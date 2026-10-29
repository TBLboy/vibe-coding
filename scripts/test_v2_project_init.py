"""Behavioral tests for the V2 project initialization script (no external packages)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/a-project-init/scripts/init_project_v2.py"
SPEC = importlib.util.spec_from_file_location("init_project_v2", SCRIPT)
assert SPEC and SPEC.loader
init = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(init)
GENERAL = (ROOT / "skills/a-project-init/templates/general-rules.md").read_text(encoding="utf-8").strip()


class InitTests(unittest.TestCase):
    def test_fresh_project_gets_full_general_rules_project_rules_and_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            result = init.initialize(project, "- 使用 `make test` 运行测试。", "team")
            self.assertEqual(result["agents_md"]["status"], "created")
            self.assertEqual(result["progress_md"]["status"], "created")
            agents = (project / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(GENERAL, agents)
            self.assertIn("八荣八耻", agents)
            self.assertIn("## 项目级规则\n\n仓库类型：团队协作仓库\n\n- 使用 `make test` 运行测试。", agents)
            self.assertTrue((project / ".vibe/progress.md").is_file())
            self.assertTrue((project / ".vibe/docs/.gitkeep").is_file())
            self.assertEqual(result["docs_dir"]["status"], "created")
            self.assertFalse((project / ".vibe/sessions").exists())
            self.assertFalse((project / ".vibe/tasks").exists())

    def test_empty_project_rules_leave_a_hint_not_invented_facts(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init.initialize(project)
            agents = (project / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(init.PROJECT_RULES_EMPTY_HINT, agents)

    def test_existing_file_is_preserved_and_rerun_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            original = "# 项目规则\r\n\r\n- 保留我的规则。\r\n"
            (project / "AGENTS.md").write_bytes(original.encode("utf-8"))
            (project / ".vibe").mkdir(); (project / ".vibe/progress.md").write_text("# mine\n", encoding="utf-8")
            first = init.initialize(project, "- 项目规则 A", "personal")
            self.assertEqual(first["agents_md"]["status"], "injected")
            self.assertEqual(first["progress_md"]["status"], "unchanged")
            self.assertEqual(first["docs_dir"]["status"], "created")
            self.assertEqual(init.initialize(project, "- 项目规则 A", "personal")["docs_dir"]["status"], "unchanged")
            content = (project / "AGENTS.md").read_bytes().decode("utf-8")
            self.assertIn(original, content)
            self.assertTrue(content.startswith(init.GENERAL_BEGIN))
            self.assertIn("仓库类型：个人仓库", content)
            second = init.initialize(project, "- 项目规则 A", "personal")
            self.assertEqual(second["agents_md"]["status"], "unchanged")
            self.assertEqual((project / "AGENTS.md").read_bytes().decode("utf-8"), content)
            self.assertEqual((project / ".vibe/progress.md").read_text(encoding="utf-8"), "# mine\n")

    def test_template_change_updates_only_the_managed_span(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            stale = f"{init.GENERAL_BEGIN}\nold rules\n{init.GENERAL_END}\n\n## 项目级规则\n\n- keep\n"
            (project / "AGENTS.md").write_text(stale, encoding="utf-8")
            result = init.initialize(project)
            self.assertEqual(result["agents_md"]["status"], "updated")
            content = (project / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn(GENERAL, content)
            self.assertNotIn("old rules", content)
            self.assertTrue(content.endswith("## 项目级规则\n\n- keep\n"))

    def test_malformed_markers_are_reported_and_file_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            broken = f"{init.GENERAL_BEGIN}\nno end marker\n"
            (project / "AGENTS.md").write_text(broken, encoding="utf-8")
            result = init.initialize(project)
            self.assertEqual(result["agents_md"]["status"], "markers-unbalanced")
            self.assertEqual((project / "AGENTS.md").read_text(encoding="utf-8"), broken)

    def test_refuses_a_nested_memory_root_unless_explicitly_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            init.initialize(root)
            child = root / "subrepo"; child.mkdir()
            with self.assertRaisesRegex(ValueError, "nested .vibe"):
                init.initialize(child)
            self.assertFalse((child / ".vibe").exists())
            self.assertFalse((child / "AGENTS.md").exists())
            init.initialize(child, allow_nested=True)
            self.assertTrue((child / ".vibe/progress.md").is_file())


if __name__ == "__main__":
    unittest.main()
