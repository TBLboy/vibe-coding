"""TASK-070: OpenCode global rules, agents, commands, and Skills surface."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
OPENCODE = ROOT / "runtime" / "opencode"
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
# controller (ALIGN-OPENCODE-002), and a real opencode 1.18.31 run verified the plugin's
# commands are registered and idle auto-continuation starts further turns
# (RESEARCH-OPENCODE-003). The runtime-specific verbs below still do not exist in OpenCode.
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
        main = parse_frontmatter(OPENCODE / "agents/vibe-main.md")
        task = main["permission"]["task"]
        self.assertEqual(task["*"], "deny")
        self.assertEqual({name for name, action in task.items() if action == "allow"}, SUBAGENTS)

        for role in SUBAGENTS:
            metadata = parse_frontmatter(OPENCODE / f"agents/{role}.md")
            self.assertEqual(metadata["permission"]["task"], {"*": "deny"}, role)

        for role in (
            "codebase-onboarder",
            "solution-researcher",
            "verification-reviewer",
            "alignment-reviewer",
            "paper-reader",
        ):
            metadata = parse_frontmatter(OPENCODE / f"agents/{role}.md")
            self.assertEqual(metadata["permission"]["edit"], "deny", role)

        for role in ("business-analyst", "workflow-distiller"):
            edit = parse_frontmatter(OPENCODE / f"agents/{role}.md")["permission"]["edit"]
            self.assertEqual(edit["*"], "deny", role)
            self.assertEqual(edit[".project-log/**"], "allow", role)

        for role in READ_ONLY_BASH_DENY_ROLES:
            metadata = parse_frontmatter(OPENCODE / f"agents/{role}.md")
            self.assertEqual(metadata["permission"]["bash"], "deny", role)

        for role in READ_ONLY_BASH_ALLOWLIST_ROLES:
            bash = parse_frontmatter(OPENCODE / f"agents/{role}.md")["permission"]["bash"]
            self.assertEqual(bash["*"], "deny", role)
            self.assertTrue(
                {pattern for pattern, action in bash.items() if action == "allow"},
                f"{role} must keep an explicit read-only allowlist",
            )

    def test_read_only_roles_can_run_the_project_interpreter(self) -> None:
        # A reviewer must be able to run the pinned interpreter and recompute hashes.
        # The `python3` on PATH can be older than what the runtime requires (3.10 vs
        # 3.11), which silently downgrades independent verification; the wrapper gives
        # the allowlist a stable path without naming a machine-specific interpreter.
        for role in ("verification-reviewer", "alignment-reviewer"):
            bash = parse_frontmatter(OPENCODE / f"agents/{role}.md")["permission"]["bash"]
            allow = {pattern for pattern, action in bash.items() if action == "allow"}
            self.assertIn(
                "*/.config/opencode/bin/vibe-python -m unittest*", allow, role
            )
            self.assertIn(
                "*/.config/opencode/bin/vibe-python runtime/scripts/validate_package.py*",
                allow, role,
            )
            self.assertIn("sha256sum *", allow, role)
            # Least privilege: the bare wrapper pattern would also permit
            # `vibe-python -c "<arbitrary python>"` for a read-only role.
            self.assertNotIn("*/.config/opencode/bin/vibe-python *", allow, role)
            # The legacy PATH-based entry points silently pick whatever python3 is
            # installed (3.10 here) and make reviews fail for environmental reasons.
            self.assertNotIn("python -m unittest*", allow, role)
            self.assertNotIn("python3 -m unittest*", allow, role)
        wrapper = OPENCODE / "bin" / "vibe-python"
        self.assertTrue(wrapper.is_file(), "bin/vibe-python entry point is missing")
        self.assertTrue(wrapper.stat().st_mode & 0o111, "bin/vibe-python must be executable")

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
        self.assertIn("0.1.51", text)
        self.assertIn("永不作为完成依据", text)
        for forbidden in (
            "CODEX_HOME", ".codex", "Codex", "TOML", "marketplace", "vibe-toolbelt",
        ):
            self.assertNotIn(forbidden, text)
        for label, pattern in FORBIDDEN_SESSION_GOAL_PATTERNS.items():
            self.assertIsNone(re.search(pattern, text), f"AGENTS.md references {label}")
        self._assert_no_session_goal_claim(text, "AGENTS.md")

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


@unittest.skipUnless(shutil.which("opencode"), "OpenCode CLI is required")
class OpenCodeIsolatedLoadTests(unittest.TestCase):
    def test_isolated_config_loads_agents_commands_and_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config"
            home = root / "home"
            shutil.copytree(OPENCODE, config)
            shutil.copytree(ROOT / "skills", config / "skills")
            global_node_modules = Path(
                os.environ.get("OPENCODE_NODE_MODULES", Path.home() / ".config/opencode/node_modules")
            )
            plugin_package = global_node_modules / "@opencode-ai/plugin"
            for relative in (".config", ".local/share", ".local/state", ".cache"):
                (home / relative).mkdir(parents=True, exist_ok=True)
            if plugin_package.is_dir():
                node_modules = config / "node_modules"
                node_modules.mkdir()
                (node_modules / "@opencode-ai").mkdir()
                os.symlink(plugin_package, node_modules / "@opencode-ai/plugin")
                sdk_package = global_node_modules / "@opencode-ai/sdk"
                if sdk_package.is_dir():
                    os.symlink(sdk_package, node_modules / "@opencode-ai/sdk")

            environment = os.environ.copy()
            environment.update({
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_DATA_HOME": str(home / ".local/share"),
                "XDG_STATE_HOME": str(home / ".local/state"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "OPENCODE_CONFIG_DIR": str(config),
            })

            resolved = subprocess.run(
                ["opencode", "debug", "config", "--pure"],
                env=environment, text=True, errors="replace", stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(resolved.returncode, 0, resolved.stdout)
            resolved_config = json.loads(resolved.stdout)
            self.assertEqual(resolved_config["default_agent"], "vibe-main")
            self.assertEqual(set(resolved_config["command"]), EXPECTED_COMMANDS)
            # `--pure` resolves config without external plugins; it proves the plugin spec is
            # resolvable but not that OpenCode imports the plugin module.
            plugins = resolved_config.get("plugin", [])
            self.assertIn(
                "@prevalentware/opencode-goal-plugin@0.1.51", plugins, plugins
            )
            local_plugins = [item for item in plugins if not str(item).startswith("@")]
            self.assertEqual(len(local_plugins), 1, plugins)
            self.assertTrue(
                Path(str(local_plugins[0]).removeprefix("file://")).is_absolute(),
                plugins,
            )

            # Non-pure debug agent performs the real plugin load in OpenCode.
            # Runtime plugin import/execution is covered by tests/test_opencode_plugin.py and the
            # non-pure OpenCode load recorded in TASK-071 evidence; a live TUI/CLI session with a
            # real model belongs to TASK-075.

            listed = subprocess.run(
                ["opencode", "debug", "skill", "--pure"],
                env=environment, text=True, errors="replace", stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(listed.returncode, 0, listed.stdout)
            # OpenCode prints full Skill bodies and truncates large stdout, so one call cannot
            # expose all 36 names. Verify every parsed runtime name belongs to the expected set,
            # no custom Skill is silently substituted, and a second isolated config that removes
            # the first page exposes exactly the remaining Skills. Together the two pages prove
            # the full set is discovered.
            expected_skills = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}
            listed_skills = set(re.findall(r'"name": "([^"]+)"', listed.stdout))
            custom_listed = listed_skills - {"customize-opencode"}
            self.assertTrue(custom_listed, "no custom Skill was discovered by the isolated config")
            self.assertLessEqual(custom_listed, expected_skills, sorted(custom_listed - expected_skills))

            discovered = set(custom_listed)
            for round_number in range(1, 5):
                missing = expected_skills - discovered
                if not missing:
                    break
                round_config = root / f"remainder-config-{round_number}"
                shutil.copytree(OPENCODE, round_config)
                round_skills = round_config / "skills"
                round_skills.mkdir()
                for name in sorted(missing):
                    shutil.copytree(ROOT / "skills" / name, round_skills / name)
                round_environment = dict(environment)
                round_environment["OPENCODE_CONFIG_DIR"] = str(round_config)
                loaded = subprocess.run(
                    ["opencode", "debug", "skill", "--pure"],
                    env=round_environment, text=True, errors="replace", stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, check=False,
                )
                self.assertEqual(loaded.returncode, 0, loaded.stdout)
                round_listed = set(re.findall(r'"name": "([^"]+)"', loaded.stdout))
                discovered |= round_listed - {"customize-opencode"}
                self.assertLessEqual(discovered, expected_skills, sorted(discovered - expected_skills))
            self.assertEqual(
                discovered, expected_skills, sorted(expected_skills - discovered),
            )

            for agent in sorted(EXPECTED_AGENTS):
                loaded = subprocess.run(
                    ["opencode", "debug", "agent", agent, "--pure"],
                    env=environment, text=True, errors="replace", stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, check=False,
                )
                self.assertEqual(loaded.returncode, 0, loaded.stdout)
                payload = json.loads(loaded.stdout)
                self.assertEqual(payload["name"], agent)
                expected_mode = "primary" if agent == "vibe-main" else "subagent"
                self.assertEqual(payload["mode"], expected_mode)

            reviewer = json.loads(subprocess.run(
                ["opencode", "debug", "agent", "verification-reviewer", "--pure"],
                env=environment, text=True, errors="replace", stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False,
            ).stdout)
            self.assertFalse(reviewer["tools"]["edit"])
            self.assertFalse(reviewer["tools"]["write"])
            bash_rules = {
                (entry["pattern"], entry["action"])
                for entry in reviewer["permission"] if entry.get("permission") == "bash"
            }
            self.assertIn(("*", "deny"), bash_rules)
            self.assertIn(("git diff*", "allow"), bash_rules)
            self.assertNotIn(("*", "ask"), bash_rules)


if __name__ == "__main__":
    unittest.main()
