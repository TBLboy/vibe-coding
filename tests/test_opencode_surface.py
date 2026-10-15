"""TASK-070: OpenCode global rules, agents, commands, and Skills surface."""
from __future__ import annotations

import base64
import fnmatch
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml


ROOT = Path(__file__).resolve().parents[1]
OPENCODE = ROOT / "runtime" / "opencode"
# Windows ships the CLI as `opencode.CMD`; CreateProcess does not apply PATHEXT
# to a bare "opencode", so resolve the real launcher once and pass its path.
OPENCODE_CLI = shutil.which("opencode")
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
EXPECTED_AGENTS = {
    "vibe-main",
    "business-analyst",
    "codebase-onboarder",
    "solution-researcher",
    "implementation-builder",
    "verification-reviewer",
    "alignment-reviewer",
    "paper-reader",
    "workflow-distiller",
}
SUBAGENTS = EXPECTED_AGENTS - {"vibe-main"}
# `/goal` is no longer forbidden: the user authorised declaring a per-client session Goal
# controller (ALIGN-OPENCODE-002). Historically, a real opencode 1.18.31 (V1) run first verified the plugin's
# commands and idle auto-continuation (RESEARCH-OPENCODE-003); on OpenCode V2 the pin moved to
# 0.1.60, which loads with status `active` (see OpenCodeIsolatedLoadTests). The runtime-specific verbs below still do not exist in OpenCode.
FORBIDDEN_SESSION_GOAL_PATTERNS = {
    "goal-bind-command": r"goal-bind",
    "goal-sync-command": r"goal-sync",
}
# Claiming a *native* session Goal in OpenCode stays forbidden: the capability comes from a
# pinned third-party plugin, not from the client. Any mention must carry a negation of that
# native framing.
FORBIDDEN_SESSION_GOAL_CLAIMS = {
    "native-goal-zh": r"原生 Goal",
    "native-goal-en": r"native Goal",
}
DECLARED_SESSION_GOAL_CONTROLLER = "@prevalentware/opencode-goal-plugin"
PINNED_SESSION_GOAL_VERSION = "0.1.60"
# A surface must not deny that the client has a session Goal capability: the
# controller is declared (ALIGN-OPENCODE-002), and a surviving denial is exactly
# how the round-1 B1 slipped through when only AGENTS.md was asserted.
FORBIDDEN_SESSION_GOAL_DENIALS = {
    "no-built-in-goal": r"no built-in session Goal",
    "no-continuation-interface": r"has no .{0,32}automatic continuation",
    "plugin-not-integrated": r"Until the TASK-\d+ plugin integration",
}
# Surfaces that must positively declare the pinned session Goal controller.
CONTROLLER_DECLARATION_SURFACES = (
    "AGENTS.md",
    "agents/vibe-main.md",
    "commands/vibe-status.md",
)
CONTROLLER_DECLARATION_SKILLS = ("a-loop-control",)
SESSION_GOAL_NEGATION = re.compile(
    r"没有|不存在|无内建|不得调用|不得宣称|不是唯一|待实现|未实现|no built-in|does not provide",
)
CLAIM_SENTENCE_BOUNDARY = re.compile(r"[\n。；;.!?]")
READ_ONLY_BASH_DENY_ROLES = {
    "business-analyst",
    "codebase-onboarder",
    "solution-researcher",
    "paper-reader",
    "workflow-distiller",
}
READ_ONLY_BASH_ALLOWLIST_ROLES = {"verification-reviewer", "alignment-reviewer"}
EXPECTED_COMMANDS = {
    "vibe-start",
    "vibe-resume",
    "vibe-plan",
    "vibe-implement",
    "vibe-verify",
    "vibe-status",
    "vibe-retro",
}


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"{path} is missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise AssertionError(f"{path} has unterminated YAML frontmatter")
    value = yaml.safe_load(text[4:end])
    if not isinstance(value, dict):
        raise AssertionError(f"{path} frontmatter is not a mapping")
    return value


def agent_rules(role: str) -> list[dict]:
    """Return the ordered V2 permission rules declared by an agent."""
    rules = parse_frontmatter(OPENCODE / f"agents/{role}.md").get("permissions")
    if not isinstance(rules, list):
        raise AssertionError(f"{role} does not declare a V2 `permissions` list")
    return rules


def resolve(rules: list[dict], action: str, resource: str) -> str | None:
    """Resolve an action/resource pair the way OpenCode V2 does.

    The last matching rule wins, so a broad deny placed first is refined by the
    narrower allows after it. `~` is expanded for path-like actions, matching the
    documented behavior for `read`, `edit`, and `external_directory`.
    """
    if action in ("read", "edit", "external_directory"):
        resource = os.path.expanduser(resource)
    effect = None
    for rule in rules:
        rule_resource = str(rule["resource"])
        if action in ("read", "edit", "external_directory"):
            rule_resource = os.path.expanduser(rule_resource)
        if fnmatch.fnmatch(action, str(rule["action"])) and fnmatch.fnmatch(resource, rule_resource):
            effect = rule["effect"]
    return effect


class OpenCodeStaticSurfaceTests(unittest.TestCase):
    def test_agents_match_the_capability_matrix(self) -> None:
        paths = sorted((OPENCODE / "agents").glob("*.md"))
        self.assertEqual({path.stem for path in paths}, EXPECTED_AGENTS)
        for path in paths:
            metadata = parse_frontmatter(path)
            self.assertTrue(metadata.get("description"), path)
            expected_mode = "primary" if path.stem == "vibe-main" else "subagent"
            self.assertEqual(metadata.get("mode"), expected_mode, path)

    def test_agent_permissions_enforce_role_boundaries(self) -> None:
        # V2 agents declare `permissions` as an ordered rule list and the LAST
        # matching rule wins, so a role boundary is only real once the rules are
        # resolved. Asserting on raw entries would have missed the drift this test
        # now guards: under the V1 `permission` mapping the compatibility layer
        # prepended a global `* * allow`, which silently granted read/webfetch/
        # websearch to every declared read-only role.
        main_rules = agent_rules("vibe-main")
        self.assertEqual(
            {name for name in SUBAGENTS if resolve(main_rules, "subagent", name) == "allow"},
            SUBAGENTS,
            "vibe-main must be able to launch every subagent",
        )

        for role in SUBAGENTS:
            rules = agent_rules(role)
            # No subagent may launch another subagent, whatever the resource.
            for target in sorted(SUBAGENTS) + ["vibe-main", "general"]:
                self.assertEqual(resolve(rules, "subagent", target), "deny", f"{role} -> {target}")
            # Baseline: an action nobody declared must not fall through to allow.
            self.assertNotEqual(resolve(rules, "browser", "*"), "allow", role)
            # Every role still has to read the code it reasons about.
            self.assertEqual(resolve(rules, "read", "src/app.py"), "allow", role)
            # Secrets stay out of reach even though `read` is broadly allowed.
            # Root-level forms are listed separately: fnmatch's `**/` requires a
            # slash, so `**/.env` does not match a project-root `.env`.
            for secret in (
                "~/.ssh/id_rsa",
                "~/.aws/credentials",
                "app/.env",
                ".env",
                ".env.local",
                "app/.env.local",
                "~/.config/opencode/opencode.json",
                "~/.config/opencode/auth.json",
            ):
                self.assertNotEqual(resolve(rules, "read", secret), "allow", f"{role}: {secret}")

        for role in (
            "codebase-onboarder",
            "solution-researcher",
            "verification-reviewer",
            "alignment-reviewer",
            "paper-reader",
        ):
            self.assertEqual(resolve(agent_rules(role), "edit", "src/app.py"), "deny", role)

        for role in ("business-analyst", "workflow-distiller"):
            rules = agent_rules(role)
            self.assertEqual(resolve(rules, "edit", "src/app.py"), "deny", role)
            self.assertEqual(resolve(rules, "edit", ".project-log/notes.md"), "allow", role)

        # Web access is a declared capability, not a default. Only the two research
        # roles may reach the network.
        for role in SUBAGENTS:
            expected = "allow" if role in {"solution-researcher", "paper-reader"} else "deny"
            for action in ("webfetch", "websearch"):
                self.assertEqual(resolve(agent_rules(role), action, "*"), expected, f"{role}/{action}")

        for role in READ_ONLY_BASH_DENY_ROLES:
            self.assertEqual(resolve(agent_rules(role), "shell", "ls"), "deny", role)

        for role in READ_ONLY_BASH_ALLOWLIST_ROLES:
            rules = agent_rules(role)
            self.assertEqual(resolve(rules, "shell", "rm -rf /"), "deny", role)
            self.assertEqual(resolve(rules, "shell", "git status"), "allow", role)

    def test_agents_declare_v2_syntax_without_a_model_pin(self) -> None:
        """Agents must use V2 `permissions` and must not pin a model.

        The legacy `permission` mapping still loads through the compatibility
        layer, but it is merged under a global `* * allow` rule, which inverts a
        declared deny into an effective allow.

        A pinned `model` names one provider/model id: it breaks on any machine
        that does not serve that exact id (delegation then fails with "Model
        unavailable"), and it silently overrides the user's configured default
        model. Without a pin a subagent inherits the parent session's model,
        which is the behaviour the user asked for; ALIGN-FW-002 records the drift.
        """
        for role in sorted(EXPECTED_AGENTS):
            metadata = parse_frontmatter(OPENCODE / f"agents/{role}.md")
            self.assertIsInstance(metadata.get("permissions"), list, role)
            self.assertNotIn("permission", metadata, f"{role} still uses V1 permission syntax")
            for legacy in ("top_p", "prompt", "tools", "disable", "maxSteps"):
                self.assertNotIn(legacy, metadata, f"{role} still sets legacy field {legacy!r}")
            # `temperature` is not dropped in V2, it moves under `request.body`
            # (migrate-v1: "temperature, top_p, and provider-specific options move
            # under request.body"). Removing it outright would change sampling for
            # every role. Note OpenCode warns that the V2 session runner preserves
            # `request` but does not yet send it with model requests.
            self.assertNotIn("temperature", metadata, f"{role} must not set top-level temperature")
            self.assertEqual(
                (metadata.get("request") or {}).get("body", {}).get("temperature"),
                0.1,
                f"{role} must keep temperature 0.1 under request.body",
            )
            self.assertNotIn(
                "model", metadata,
                f"{role} must not pin a model: it breaks off this machine and overrides "
                f"the user's default model (ALIGN-FW-002)",
            )
            for rule in metadata["permissions"]:
                self.assertEqual(
                    sorted(rule), ["action", "effect", "resource"], f"{role}: malformed rule {rule}"
                )
                self.assertIn(rule["effect"], ("allow", "ask", "deny"), role)

    def test_installer_template_declares_no_legacy_permission_block(self) -> None:
        """A top-level V1 `permission` block leaks into every agent.

        It is expanded into a global `* * allow` rule plus a global subagent
        allowlist, which is applied before agent rules; that is what granted
        read-only roles web access and let every subagent inherit the launcher
        allowlist. Role boundaries belong in the agent files.
        """
        config = json.loads((OPENCODE / "opencode.json").read_text(encoding="utf-8"))
        self.assertNotIn("permission", config)

    def test_read_only_roles_can_run_the_project_interpreter(self) -> None:
        # A reviewer must be able to run the pinned interpreter and recompute hashes.
        # The `python3` on PATH can be older than what the runtime requires (3.10 vs
        # 3.11), which silently downgrades independent verification; the wrapper gives
        # the allowlist a stable path without naming a machine-specific interpreter.
        #
        # V3 PR-04 replaced the raw `-m unittest` allow with the trusted verification
        # runner, and PR-06 made that pattern cross-platform: the installed wrapper is a
        # POSIX script, so pinning the allowlist to it left a Windows reviewer unable to
        # run anything at all. The pattern is anchored to the runner and its subcommand,
        # and the runner itself refuses an interpreter below the supported version, so
        # allowing any interpreter cannot silently downgrade a review. Digest
        # re-derivation goes through the same entry point (`run --action hash`), so the
        # allowlist no longer advertises `sha256sum`: a permission entry for a command
        # that does not exist on this platform is a capability the reviewer cannot use.
        for role in ("verification-reviewer", "alignment-reviewer"):
            rules = agent_rules(role)
            allow = {
                str(rule["resource"])
                for rule in rules
                if rule["action"] == "shell" and rule["effect"] == "allow"
            }
            self.assertIn(
                "*verification_runner.py preflight*",
                allow, role,
            )
            self.assertIn(
                "*verification_runner.py run*",
                allow, role,
            )
            self.assertFalse(
                [pattern for pattern in allow if "sha256sum" in pattern],
                f"{role} still advertises a POSIX-only hashing tool",
            )
            # Least privilege: the bare wrapper pattern would also permit
            # `vibe-python -c "<arbitrary python>"` for a read-only role.
            self.assertNotIn("*/.config/opencode/bin/vibe-python *", allow, role)
            # The legacy PATH-based entry points silently pick whatever python3 is
            # installed (3.10 here) and make reviews fail for environmental reasons.
            self.assertNotIn("python -m unittest*", allow, role)
            self.assertNotIn("python3 -m unittest*", allow, role)
            # A raw test-command wildcard admits any command while looking like a
            # capability check; the runner's action registry is the replacement.
            for forbidden in ("*pytest*", "* -m pytest*", "* -m unittest*"):
                self.assertNotIn(forbidden, allow, role)
        wrapper = OPENCODE / "bin" / "vibe-python"
        self.assertTrue(wrapper.is_file(), "bin/vibe-python entry point is missing")
        # Windows has no POSIX permission bits, so the executable-bit check is
        # POSIX-only; the file-exists assertion above still runs everywhere.
        if os.name == "posix":
            self.assertTrue(wrapper.stat().st_mode & 0o111, "bin/vibe-python must be executable")

    def test_read_only_history_forms_resolve_to_allow(self) -> None:
        """History queries with flags must stay allowed through the plain `git log*` pattern.

        `git log --format=*` and `git log --pretty=*` were listed explicitly after a session
        reported the matcher mishandling `--flag=value` queries; a later session found the
        plain `git log*` already matched them, i.e. they were redundant insurance rather than
        a fix, and they were removed on 2026-10-15. What is worth pinning is the resolved
        effect of a real command, not a literal copy of the pattern list: the literal
        assertions kept passing while saying nothing about whether the command is permitted.
        """
        for role in ("verification-reviewer", "alignment-reviewer"):
            rules = agent_rules(role)
            allow = {
                str(rule["resource"])
                for rule in rules
                if rule["action"] == "shell" and rule["effect"] == "allow"
            }
            for pattern in ("git log*", "git show*", "git rev-parse*"):
                self.assertIn(pattern, allow, role)
            # The flag-bearing forms the removed entries used to cover must still resolve.
            for command in (
                "git log --format=%H -1",
                "git log --pretty=oneline -1",
                "git log --oneline -1",
                "git show HEAD",
                "git rev-parse HEAD",
            ):
                self.assertEqual(resolve(rules, "shell", command), "allow", f"{role}: {command}")
            # Still read-only: resolved effect, not just the literal pattern list.
            for command in ("git commit -m x", "git push origin main", "git reset --hard", "git checkout ."):
                self.assertNotEqual(resolve(rules, "shell", command), "allow", f"{role}: {command}")

    def test_read_only_roles_may_inspect_the_installed_control_layer(self) -> None:
        """Verification needs the deployed layer, not only the source template.

        A path outside the Location is gated by the separate `external_directory`
        action before its `read`, so allowing `read` alone is not enough; and the
        secret denies must stay last so that they still win (TASK-140).
        """
        installed = "~/.config/opencode/agents/verification-reviewer.md"
        for role in ("verification-reviewer", "alignment-reviewer"):
            rules = agent_rules(role)
            self.assertEqual(resolve(rules, "external_directory", installed), "allow", role)
            self.assertEqual(resolve(rules, "read", installed), "allow", role)
            # The allow is per subdirectory: `grep`'s resource is its pattern, not its
            # search path, so a directory-wide allow would expose the secrets below to
            # the grep tool. Anything outside an allowed boundary must not resolve to
            # `external_directory: allow`.
            for outside in (
                "~/.config/opencode/opencode.json",
                "~/.config/opencode/opencode.json.bak-20261012-225139",
                "~/.config/opencode/service.json",
                "~/.config/opencode/backups/update-20261012-224224/opencode.json",
                "~/.config/opencode/memory/notes.md",
            ):
                self.assertNotEqual(
                    resolve(rules, "external_directory", outside), "allow", f"{role}: {outside}"
                )
            self.assertNotEqual(
                resolve(rules, "shell", "git diff --no-index x y"), "allow", role
            )
            # `external_directory` resources are directory boundaries: a literal
            # top-level file entry is inert in the runtime matcher, so keep every
            # allow wildcard-shaped or it silently does nothing.
            for rule in rules:
                if rule["action"] == "external_directory" and rule["effect"] == "allow":
                    self.assertTrue(
                        str(rule["resource"]).endswith("/*"),
                        f"{role}: external_directory allow must be a directory boundary: {rule}",
                    )
            for secret in (
                "~/.config/opencode/opencode.json",
                "~/.config/opencode/opencode.json.bak-20261012-225139",
                "~/.config/opencode/auth.json",
                "~/.config/opencode/service.json",
                "~/.config/opencode/backups/update-20261012-224224/opencode.json",
                "~/.config/opencode/memory/notes.md",
                "~/.ssh/id_rsa",
                "~/.aws/credentials",
            ):
                self.assertNotEqual(resolve(rules, "read", secret), "allow", f"{role}: {secret}")

    def test_primary_agent_exposes_installed_plugins_and_mcp_tools(self) -> None:
        """Installed plugin and MCP tools must reach the primary agent's session.

        Plugin tools are V2 actions named after the tool and MCP tools are
        `<server>_<tool>`; OpenCode hides every action that resolves to `deny`, so a
        catch-all `* * deny` baseline silently removes whatever the user installed.
        That is what hid the goal plugin's tools while its own reminder still reached
        the prompt (ALIGN-FW-008). The primary agent therefore carries no catch-all
        deny, while restricted roles keep theirs on purpose.
        """
        main = agent_rules("vibe-main")
        self.assertNotIn(
            {"action": "*", "resource": "*", "effect": "deny"}, main,
            "a catch-all deny hides every installed plugin and MCP tool",
        )
        # OpenCode's documented base policy, prepended the way the runtime orders it.
        base = [
            {"action": "*", "resource": "*", "effect": "allow"},
            {"action": "external_directory", "resource": "*", "effect": "ask"},
            {"action": "read", "resource": "*.env", "effect": "ask"},
            {"action": "read", "resource": "*.env.*", "effect": "ask"},
            {"action": "read", "resource": "*.env.example", "effect": "allow"},
        ]
        ordered = [*base, *main]
        for action in ("get_goal", "create_goal", "update_goal_plan", "list_all_goals",
                       "memory_set", "memory_get", "context7_resolve-library-id",
                       "wikipedia_search", "playwright_navigate", "web-search_search"):
            self.assertEqual(resolve(ordered, action, "*"), "allow", action)
        for role in ("business-analyst", "verification-reviewer"):
            rules = agent_rules(role)
            for action in ("get_goal", "memory_set", "wikipedia_search"):
                self.assertNotEqual(resolve(rules, action, "*"), "allow", f"{role}: {action}")

    def test_commands_are_thin_primary_agent_entrypoints(self) -> None:
        paths = sorted((OPENCODE / "commands").glob("*.md"))
        self.assertEqual({path.stem for path in paths}, EXPECTED_COMMANDS)
        for path in paths:
            metadata = parse_frontmatter(path)
            self.assertEqual(metadata.get("agent"), "vibe-main", path)
            self.assertNotEqual(metadata.get("subtask"), True, path)
            self.assertIn("$ARGUMENTS", path.read_text(encoding="utf-8"), path)

    def test_global_rules_are_opencode_native(self) -> None:
        text = (OPENCODE / "AGENTS.md").read_text(encoding="utf-8")
        for required in (
            "八荣八耻",
            "business-clarification",
            "quick",
            "standard",
            "strict",
            "OPENCODE_CONFIG_DIR",
            "OpenCode `task` 工具",
            "Project Goal",
            "127.0.0.1:10808",
        ):
            self.assertIn(required, text)
        # The authorised contract (ALIGN-OPENCODE-002): a declared per-client controller,
        # pinned, with the plugin state explicitly excluded from completion evidence.
        self.assertIn(DECLARED_SESSION_GOAL_CONTROLLER, text)
        self.assertIn(PINNED_SESSION_GOAL_VERSION, text)
        self.assertIn("永不作为完成依据", text)
        for forbidden in (
            "CODEX_HOME", ".codex", "Codex", "TOML", "marketplace", "vibe-toolbelt",
        ):
            self.assertNotIn(forbidden, text)
        for label, pattern in FORBIDDEN_SESSION_GOAL_PATTERNS.items():
            self.assertIsNone(re.search(pattern, text), f"AGENTS.md references {label}")
        self._assert_no_session_goal_claim(text, "AGENTS.md")

    def test_session_goal_controller_is_declared_on_every_required_surface(self) -> None:
        """Every surface that talks about session Goal must name the pinned controller."""
        for relative in CONTROLLER_DECLARATION_SURFACES:
            text = (OPENCODE / relative).read_text(encoding="utf-8")
            self.assertIn(DECLARED_SESSION_GOAL_CONTROLLER, text, relative)
            self.assertIn(PINNED_SESSION_GOAL_VERSION, text, relative)
        for name in CONTROLLER_DECLARATION_SKILLS:
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(DECLARED_SESSION_GOAL_CONTROLLER, text, name)
            self.assertIn(PINNED_SESSION_GOAL_VERSION, text, name)

    def test_no_surface_denies_the_session_goal_capability(self) -> None:
        """A denial of the capability contradicts the controller the surface declares."""
        paths = [OPENCODE / "AGENTS.md", OPENCODE / "README.md"]
        paths += sorted((OPENCODE / "agents").glob("*.md"))
        paths += sorted((OPENCODE / "commands").glob("*.md"))
        paths += sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertTrue(paths)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for label, pattern in FORBIDDEN_SESSION_GOAL_DENIALS.items():
                self.assertIsNone(
                    re.search(pattern, text), f"{path} denies the session Goal capability: {label}"
                )

    def test_every_surface_avoids_native_goal_claims(self) -> None:
        """The native-Goal rule also covers agents, commands and the module README."""
        paths = [OPENCODE / "AGENTS.md", OPENCODE / "README.md"]
        paths += sorted((OPENCODE / "agents").glob("*.md"))
        paths += sorted((OPENCODE / "commands").glob("*.md"))
        self.assertTrue(paths)
        for path in paths:
            self._assert_no_session_goal_claim(path.read_text(encoding="utf-8"), str(path))

    def _assert_no_session_goal_claim(self, text: str, label: str) -> None:
        for name, pattern in FORBIDDEN_SESSION_GOAL_CLAIMS.items():
            for match in re.finditer(pattern, text):
                start = match.start()
                while start > 0 and not CLAIM_SENTENCE_BOUNDARY.search(text[start - 1]):
                    start -= 1
                end = match.end()
                while end < len(text) and not CLAIM_SENTENCE_BOUNDARY.search(text[end]):
                    end += 1
                window = text[start:end]
                self.assertTrue(
                    SESSION_GOAL_NEGATION.search(window),
                    f"{label} mentions {name} without a negation marker: {window!r}",
                )

    def test_opencode_surface_does_not_reference_unimplemented_goal_commands(self) -> None:
        paths = [OPENCODE / "AGENTS.md", OPENCODE / "agents/vibe-main.md"]
        paths += sorted((OPENCODE / "commands").glob("*.md"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for label, pattern in FORBIDDEN_SESSION_GOAL_PATTERNS.items():
                self.assertIsNone(re.search(pattern, text), f"{path} references {label}")

    def test_all_skills_avoid_unavailable_session_goal_claims(self) -> None:
        for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
            self._assert_no_session_goal_claim(path.read_text(encoding="utf-8"), str(path))

    def test_all_skills_declare_opencode_compatibility(self) -> None:
        paths = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertTrue(paths)
        for path in paths:
            metadata = parse_frontmatter(path)
            self.assertEqual(metadata.get("name"), path.parent.name, path)
            self.assertEqual(metadata.get("compatibility"), "opencode", path)


def opencode_major() -> int | None:
    if not OPENCODE_CLI:
        return None
    try:
        result = subprocess.run(
            [OPENCODE_CLI, "--version"], text=True, errors="replace", stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, check=False, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"(\d+)\.\d+\.\d+", result.stdout)
    return int(match.group(1)) if match else None


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return handle.getsockname()[1]


@unittest.skipUnless(OPENCODE_CLI, "OpenCode CLI is required")
class OpenCodeIsolatedLoadTests(unittest.TestCase):
    """Install into an isolated config and let a real OpenCode V2 server load it."""

    PASSWORD = "vibe-isolated-load"

    def _get(self, port: int, path: str, directory: Path) -> list:
        query = urlencode({"directory": str(directory)})
        request = Request(f"http://127.0.0.1:{port}{path}?{query}")
        token = base64.b64encode(f"opencode:{self.PASSWORD}".encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
        with urlopen(request, timeout=60) as response:  # noqa: S310 - loopback only
            return json.loads(response.read().decode("utf-8"))["data"]

    def test_installed_config_loads_plugins_agents_commands_and_skills(self) -> None:
        major = opencode_major()
        if major is None or major < 2:
            self.skipTest(f"OpenCode V2 CLI is required (found major version {major})")
        with tempfile.TemporaryDirectory() as temporary:
            # On macOS `TMPDIR` lives under `/var`, which is a symlink to `/private/var`,
            # while the runtime canonicalises the config path it reports back from
            # `/api/plugin`. Comparing a raw `mkdtemp` path with a canonical one failed on
            # macOS only (the CI runner is Linux, where `/tmp` is not a symlink), so the
            # whole isolated-load test was unusable as a local gate.
            root = Path(temporary).resolve()
            config = root / "config"
            home = root / "home"
            project = root / "project"
            (project / ".project-log").mkdir(parents=True)
            for relative in (".config", ".local/share", ".local/state", ".cache"):
                (home / relative).mkdir(parents=True, exist_ok=True)
            installed = subprocess.run(
                [sys.executable, str(ROOT / "scripts/opencode_installer.py"), "install",
                 "--opencode-home", str(config), "--skip-preflight"],
                text=True, errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout)

            environment = os.environ.copy()
            environment.update({
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_STATE_HOME": str(home / ".local/state"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "OPENCODE_CONFIG_DIR": str(config),
                "OPENCODE_SERVER_PASSWORD": self.PASSWORD,
            })
            port = free_port()
            log = (root / "serve.log").open("w", encoding="utf-8")
            server = subprocess.Popen(
                [OPENCODE_CLI, "serve", "--hostname", "127.0.0.1", "--port", str(port), "--print-logs"],
                cwd=project, env=environment, stdout=log, stderr=subprocess.STDOUT,
            )
            try:
                plugins: dict[str, dict] = {}
                # The Goal controller is fetched from npm on first load, so allow time for it.
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    try:
                        listed = self._get(port, "/api/plugin", project)
                    except (OSError, ValueError):
                        time.sleep(1)
                        continue
                    # A plugin still being loaded can appear without an `id`;
                    # indexing it directly made this poll loop fail intermittently.
                    plugins = {
                        item["id"]: item
                        for item in listed
                        if item.get("id") and item.get("source", {}).get("type") != "builtin"
                    }
                    if "vibe-workflow" in plugins and len(plugins) >= 2:
                        break
                    time.sleep(2)
                log.flush()
                serve_log = (root / "serve.log").read_text(encoding="utf-8", errors="replace")
                # The `goal` and `memory` plugins are fetched from npm on first load. In a
                # sandbox with no registry route that fetch fails, which is an environment
                # gap rather than a plugin defect (the same reason the Goal-controller check
                # below skips). Only a load failure that is not an npm-install failure means
                # a plugin we ship is broken.
                load_failures = [
                    line for line in serve_log.splitlines()
                    if "failed to load plugin" in line and "NpmInstallFailedError" not in line
                ]
                self.assertEqual(load_failures, [], "\n".join(load_failures))
                self.assertIn("vibe-workflow", plugins, serve_log[-4000:])
                self.assertEqual(plugins["vibe-workflow"]["state"]["status"], "active")
                self.assertEqual(
                    plugins["vibe-workflow"]["source"]["path"],
                    str(config / "plugins" / "vibe-workflow" / "index.ts"),
                )
                goal = [item for item in plugins.values() if item["source"].get("type") == "package"]
                if not goal:
                    self.skipTest("the session Goal controller could not be fetched from npm in time")
                self.assertEqual(goal[0]["source"]["target"], "@prevalentware/opencode-goal-plugin@0.1.60")
                self.assertEqual(goal[0]["state"]["status"], "active")
                # The plugin resolved the project root and the installed runtime at setup.
                self.assertIn(f'"root":{json.dumps(str(project))}', serve_log)

                agents = {item["id"]: item for item in self._get(port, "/api/agent", project)}
                self.assertLessEqual(EXPECTED_AGENTS, set(agents))
                for agent in EXPECTED_AGENTS:
                    expected_mode = "primary" if agent == "vibe-main" else "subagent"
                    self.assertEqual(agents[agent]["mode"], expected_mode, agent)
                # Assert the resolved effect, not the literal rules: V2 applies the
                # last matching rule, and global config is merged ahead of agent
                # rules. A literal-rule assertion passed while the compatibility
                # layer's global `* * allow` was silently granting read-only roles
                # network access and secret reads.
                reviewer = agents["verification-reviewer"]["permissions"]
                self.assertEqual(resolve(reviewer, "edit", "src/app.py"), "deny")
                self.assertEqual(resolve(reviewer, "shell", "rm -rf /"), "deny")
                self.assertEqual(resolve(reviewer, "shell", "git diff"), "allow")
                self.assertEqual(resolve(reviewer, "read", "src/app.py"), "allow")
                for action in ("webfetch", "websearch"):
                    self.assertEqual(resolve(reviewer, action, "*"), "deny", action)
                for role in EXPECTED_AGENTS - {"vibe-main"}:
                    rules = agents[role]["permissions"]
                    self.assertEqual(resolve(rules, "subagent", "paper-reader"), "deny", role)
                    self.assertNotEqual(
                        resolve(rules, "read", str(home / ".ssh" / "id_rsa")), "allow", role
                    )
                self.assertEqual(
                    resolve(agents["vibe-main"]["permissions"], "subagent", "paper-reader"), "allow"
                )
                for role in EXPECTED_AGENTS:
                    # No agent pins a model, so the live view reports none of its own
                    # and the role inherits the session model (ALIGN-FW-002).
                    self.assertIsNone(agents[role].get("model"), role)

                commands = {item.get("id") or item.get("name") for item in self._get(port, "/api/command", project)}
                self.assertLessEqual(EXPECTED_COMMANDS, commands)

                skills = {item.get("id") or item.get("name") for item in self._get(port, "/api/skill", project)}
                expected_skills = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}
                self.assertLessEqual(expected_skills, skills, sorted(expected_skills - skills))
            finally:
                server.terminate()
                try:
                    server.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    server.kill()
                log.close()

if __name__ == "__main__":
    unittest.main()
