"""TASK-042: user-visible rules point at the promoted command surface."""
from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DocumentationConsistencyTests(unittest.TestCase):
    def test_usage_describes_the_formal_surface(self) -> None:
        text = (ROOT / "docs/USAGE.md").read_text(encoding="utf-8")
        for command in (
            "task create|reopen|begin|update|wait|resume|handoff|finish|cancel",
            "record create|update|link",
            "evidence record|invalidate|refresh",
            "review record",
            "goal create|update|cancel|complete",
            "workspace clear|status|history",
            "verification preflight|run",
        ):
            self.assertIn(command, text)
        # A capability that exists only in the CLI is not documented. V3 added several,
        # so the guide is asserted against them instead of being trusted to keep up.
        for phrase in (
            "bound_document", "informational_ref", "workspace_generation",
            "verification_capability_missing", "reopens", "open-question",
            "execution_state", "verification_state", "review_verdict",
        ):
            self.assertIn(phrase, text, phrase)
        self.assertNotIn("尚未接入", text)
        self.assertNotIn("自动 apply 按迁移状态机实施", text)
        # The migration tool and the retired compatibility entry are gone.
        self.assertNotIn("migrate preview|apply|resume|rollback", text)
        self.assertNotIn("loopctl", text)

    def test_opencode_global_prompt_initializes_format_two_through_vibe(self) -> None:
        """The shipped global prompt must send the agent through the formal entry.

        This used to read `prompts/vibe-global-agent.md`, the codex prompt. That prompt
        and the rest of the codex delivery face were removed; the OpenCode surface's
        global prompt is `runtime/opencode/AGENTS.md`.
        """
        text = (ROOT / "runtime/opencode/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("scripts/vibe.py", text)
        self.assertIn("init", text)
        self.assertIn("format 2", text)
        self.assertNotIn("scripts/init_project.py\" --target", text)

    def test_project_skills_point_to_formal_init(self) -> None:
        init_skill = (ROOT / "skills/a-project-init/SKILL.md").read_text(encoding="utf-8")
        log_skill = (ROOT / "skills/a-project-log/SKILL.md").read_text(encoding="utf-8")
        reference = (ROOT / "skills/a-project-log/REFERENCE.md").read_text(encoding="utf-8")
        self.assertIn("format 2", init_skill)
        self.assertIn("scripts/vibe.py", log_skill)
        self.assertIn("format 2", reference)
        self.assertNotIn("migration window", reference)

    def test_user_docs_point_at_the_opencode_entry(self) -> None:
        """The OpenCode entry must be the only installer a reader can reach.

        A review of TASK-076 found docs/USAGE.md still telling readers to run the
        root ./install.sh, which installed the *codex* client to ~/.codex. The same
        class of drift had already slipped through once (TASK-080 B-b), so the entry
        point is asserted here instead of being trusted to stay correct. The codex
        delivery face has since been removed outright (TASK-126), so the assertion is
        now also that the misleading files are gone rather than merely unmentioned.
        """
        entry = "runtime/opencode/install.sh"
        for relative in ("README.md", "docs/USAGE.md", "AI_INSTALL.md", "AI_UPGRADE.md"):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(entry, text, relative)
            self.assertNotIn("global_installer.py verify", text, relative)
            self.assertNotIn("codex mcp list", text, relative)
            self.assertIsNone(
                re.search(r"(?m)^\s*\./install\.sh\b", text),
                f"{relative} still directs the reader at the codex-surface root installer",
            )
        for relative in (
            "install.sh", "install.ps1", "update.sh", "update.ps1",
            "uninstall.sh", "uninstall.ps1", "scripts/global_installer.py",
            "build_release.py", "cc-switch-common-config-codex.txt",
            "prompts/vibe-global-agent.md", "runtime/agents/roles.json",
            "runtime/hooks/session_start.py", "runtime/mcp/optional-mcps.json",
            "plugins/vibe-toolbelt/.codex-plugin/plugin.json",
            ".agents/plugins/marketplace.json",
        ):
            self.assertFalse(
                (ROOT / relative).exists(),
                f"{relative} is part of the removed codex delivery face",
            )

    def test_no_bare_format_number_naming(self) -> None:
        """Bare `Format N` must not reappear anywhere in the shipped surface.

        docs/TERMINOLOGY.md forbids it: "Format N" conflates an architecture
        generation name with the persisted `format` field, which is what led an
        agent to read `format 2` as a storage/layout mode. A cleanup round removed
        the nine remaining uses; this keeps them from coming back.
        """
        pattern = re.compile(r"\bFormat\s+[0-9]+\b")
        allowed = {"docs/TERMINOLOGY.md"}  # the contract itself quotes the banned form
        suffixes = {".py", ".md", ".json", ".ts", ".yaml", ".yml"}
        offenders = []
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative in allowed or relative.startswith((".git/", ".opencode/", "node_modules/")):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            for match in pattern.finditer(text):
                offenders.append(f"{relative}: {match.group(0)!r}")
        self.assertEqual(offenders, [], f"bare Format N naming reappeared: {offenders}")

    def test_docs_do_not_advertise_retired_commands(self) -> None:
        """A retired command must not stay in the user guide.

        TASK-093 removed exchange; USAGE.md kept teaching the full command surface,
        which the final review flagged as a blocking alignment conflict. Naming the
        command in a "retired" explanation is fine; a usable invocation is not.
        """
        text = (ROOT / "docs/USAGE.md").read_text(encoding="utf-8")
        for retired in ("state-export", "state-import", "state-exchange"):
            self.assertIsNone(
                re.search(rf"--root <[^>]+>\s+{retired}", text),
                f"USAGE.md still shows a usable {retired} invocation",
            )
        self.assertIsNone(
            re.search(r"^\s*--root <[^>]+> exchange\b", text, re.M),
            "USAGE.md still shows a usable exchange invocation",
        )

    def test_readme_and_install_guide_use_the_formal_entry(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        install = (ROOT / "AI_INSTALL.md").read_text(encoding="utf-8")
        self.assertNotIn('init_project.py" --target', readme)
        self.assertNotIn("loopctl init", readme)
        self.assertNotIn('init_project.py" --target', install)
        self.assertIn('vibe.py" init', readme)
        self.assertIn('vibe.py" init', install)


if __name__ == "__main__":
    unittest.main()
