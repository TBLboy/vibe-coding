from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from init_project import initialize_project


PROGRESS_REQUIRED = (
    "最新在最上",
    "当前状态",
    "docs/archive",
    "50-100 KB",
    "单一事实源",
    "loop/handoff.md",
    "机器文件不手工重排",
)

CURRENT_SESSION_REQUIRED = (
    "最新在最上",
    "当前状态",
    "docs/archive",
    "50-100 KB",
    "单一事实源",
    "loop/active-run.yaml",
    "机器文件不手工重排",
)


class ProjectLogTemplateConventionsTests(unittest.TestCase):
    def test_progress_template_documents_conventions(self) -> None:
        content = (ROOT / "runtime/project-log-template/progress.md").read_text(encoding="utf-8")
        for marker in PROGRESS_REQUIRED:
            self.assertIn(marker, content, f"progress.md missing convention marker: {marker}")

    def test_current_session_template_documents_conventions(self) -> None:
        content = (ROOT / "runtime/project-log-template/current-session.md").read_text(encoding="utf-8")
        for marker in CURRENT_SESSION_REQUIRED:
            self.assertIn(marker, content, f"current-session.md missing convention marker: {marker}")

    def test_initialized_project_copies_convention_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            initialize_project(target)
            progress = target / ".project-log/progress.md"
            current = target / ".project-log/current-session.md"
            archive_readme = target / ".project-log/docs/archive/README.md"
            self.assertTrue(progress.is_file())
            self.assertTrue(current.is_file())
            self.assertTrue(archive_readme.is_file())
            for marker in PROGRESS_REQUIRED:
                self.assertIn(marker, progress.read_text(encoding="utf-8"))
            for marker in CURRENT_SESSION_REQUIRED:
                self.assertIn(marker, current.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
