"""TASK-042: user-visible rules point at the promoted command surface."""
from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DocumentationConsistencyTests(unittest.TestCase):
    def test_usage_describes_formal_surface_and_explicit_migration(self) -> None:
        text = (ROOT / "docs/USAGE.md").read_text(encoding="utf-8")
        for command in (
            "task begin|update|wait|resume|handoff|finish|cancel",
            "record create|update|link",
            "evidence record|invalidate|refresh",
            "review record",
            "goal update|complete",
            "migrate preview|apply|resume|rollback",
        ):
            self.assertIn(command, text)
        self.assertNotIn("尚未接入", text)
        self.assertNotIn("自动 apply 按迁移状态机实施", text)

    def test_global_prompt_initializes_format_two_through_vibe(self) -> None:
        text = (ROOT / "prompts/vibe-global-agent.md").read_text(encoding="utf-8")
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
        self.assertIn("migration window", reference)

    def test_user_docs_point_at_the_opencode_entry(self) -> None:
        """The OpenCode entry must not be displaced by the retained codex surface.

        A review of TASK-076 found docs/USAGE.md still telling readers to run the
        root ./install.sh, which installs the *codex* client to ~/.codex. The same
        class of drift had already slipped through once (TASK-080 B-b), so the entry
        point is asserted here instead of being trusted to stay correct.
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
