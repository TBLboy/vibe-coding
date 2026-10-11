import json
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
        marker = self.target / ".project-log" / "state-format.json"
        self.assertTrue(marker.exists())
        self.assertEqual(json.loads(marker.read_text(encoding="utf-8"))["format"], 2)

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

    def test_idempotent_unchanged(self):
        ipa.initialize(self.target, project_rules="")
        agents = self.target / "AGENTS.md"
        before = agents.read_text(encoding="utf-8")
        result = ipa.initialize(self.target, project_rules="")
        self.assertEqual(result["agents_md"]["status"], "unchanged")
        after = agents.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_existing_block_is_updated_when_the_template_changes(self):
        """The skill's instruction ("change the template, re-initialize") has to work.

        Re-initializing used to report `skipped` whenever the begin marker existed, so an
        updated general rule could never reach a project that already had a block.
        """
        rules = "## 模块边界\n\n- 只修改 dexbot_bringup。"
        ipa.initialize(self.target, project_rules=rules)
        agents = self.target / "AGENTS.md"
        before = agents.read_text(encoding="utf-8")

        original = ipa.load_general_template
        ipa.load_general_template = lambda: original() + "\n9. 新规则：模板更新必须能传播。\n"
        try:
            result = ipa.initialize(self.target, project_rules="")
        finally:
            ipa.load_general_template = original

        self.assertEqual(result["agents_md"]["status"], "updated")
        after = agents.read_text(encoding="utf-8")
        self.assertIn("新规则：模板更新必须能传播。", after)
        self.assertNotIn("新规则：模板更新必须能传播。", before)
        # Only the managed span moves: the project's own rules survive verbatim.
        self.assertIn(rules, after)
        self.assertIn("## 项目级规则", after)
        self.assertLess(after.index(ipa.GENERAL_END), after.index("## 项目级规则"))

    def test_unbalanced_markers_are_left_alone(self):
        """A begin marker without its end marker must not be guessed at."""
        content = f"# 项目规则\n\n{ipa.GENERAL_BEGIN}\n1. 半截块\n\n## 我自己的章节\n\n- 别删我\n"
        (self.target / "AGENTS.md").write_text(content, encoding="utf-8")
        result = ipa.initialize(self.target, project_rules="")
        self.assertEqual(result["agents_md"]["status"], "markers-unbalanced")
        self.assertEqual((self.target / "AGENTS.md").read_text(encoding="utf-8"), content)

    def test_update_keeps_bytes_outside_the_block(self):
        """Bytes outside the managed block must survive, including their line endings.

        `Path.read_text`/`write_text` use universal newlines, so on Windows any write turns
        every line ending in the file into CRLF -- including the project's own text that this
        function promises to leave alone.
        """
        body = "# 项目规则\n\n- 我自己的行尾是 LF\n"
        agents = self.target / "AGENTS.md"
        agents.write_bytes(
            (ipa.general_block(ipa.load_general_template()) + "\n" + body).encode("utf-8")
        )
        before = agents.read_bytes()

        original = ipa.load_general_template
        ipa.load_general_template = lambda: original() + "\n9. 新规则：模板更新必须能传播。\n"
        try:
            result = ipa.initialize(self.target, project_rules="")
        finally:
            ipa.load_general_template = original

        self.assertEqual(result["agents_md"]["status"], "updated")
        after = agents.read_bytes()
        self.assertNotEqual(before, after)
        self.assertTrue(after.endswith(body.encode("utf-8")))
        self.assertNotIn(b"\r\n", after)

    def test_a_second_begin_marker_inside_the_span_is_reported(self):
        """Two begins with one end means the span is not the block this code assumes.

        Replacing that span would swallow the inner begin marker, so it must report instead.
        """
        content = (
            f"{ipa.GENERAL_BEGIN}\n1. 旧\n{ipa.GENERAL_BEGIN}\n1. 更旧\n"
            f"{ipa.GENERAL_END}\n\n## 项目级规则\n"
        )
        agents = self.target / "AGENTS.md"
        agents.write_text(content, encoding="utf-8")
        before = agents.read_bytes()
        result = ipa.initialize(self.target, project_rules="")
        self.assertEqual(result["agents_md"]["status"], "markers-ambiguous")
        self.assertEqual(agents.read_bytes(), before)

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
