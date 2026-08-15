import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "a-project-init" / "scripts" / "init_project_agents.py"
sys.path.insert(0, str(SCRIPT.parent))
import init_project_agents as ipa


class ProjectInitAgentsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_fresh_project(self):
        result = ipa.initialize(self.target, project_rules="")
        self.assertEqual(result["project_log"]["status"], "created")
        self.assertEqual(result["agents_md"]["status"], "created")
        agents = self.target / "AGENTS.md"
        content = agents.read_text(encoding="utf-8")
        self.assertTrue(agents.exists())
        self.assertIn(ipa.GENERAL_BEGIN, content)
        self.assertIn(ipa.GENERAL_END, content)
        self.assertIn("## 项目级规则", content)
        self.assertIn(ipa.PROJECT_RULES_EMPTY_HINT, content)
        self.assertTrue((self.target / ".project-log" / "workflow.yaml").exists())

    def test_create_with_project_rules(self):
        rules = "## 模块边界\n\n- 主线只修改 dexbot_bringup。"
        result = ipa.initialize(self.target, project_rules=rules)
        self.assertEqual(result["project_rules_status"], "provided")
        content = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## 模块边界", content)
        self.assertIn("dexbot_bringup", content)

    def test_inject_into_existing_agents_md(self):
        existing = "# 项目规则\n\n- 原有内容保留"
        (self.target / "AGENTS.md").write_text(existing, encoding="utf-8")
        result = ipa.initialize(self.target, project_rules="")
        self.assertEqual(result["agents_md"]["status"], "injected")
        content = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith(ipa.GENERAL_BEGIN))
        self.assertIn(existing, content)

    def test_idempotent_skip(self):
        ipa.initialize(self.target, project_rules="")
        agents = self.target / "AGENTS.md"
        before = agents.read_text(encoding="utf-8")
        result = ipa.initialize(self.target, project_rules="")
        self.assertEqual(result["agents_md"]["status"], "skipped")
        after = agents.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_dry_run_writes_nothing(self):
        result = ipa.initialize(self.target, project_rules="", dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertFalse((self.target / "AGENTS.md").exists())
        self.assertFalse((self.target / ".project-log").exists())

    def test_project_log_skipped_when_exists(self):
        (self.target / ".project-log").mkdir()
        result = ipa.initialize(self.target, project_rules="")
        self.assertEqual(result["project_log"]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
