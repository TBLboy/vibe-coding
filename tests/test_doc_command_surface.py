"""Documented commands must be runnable as written.

Two install-time defects slipped through because nothing executed the documentation:
`vibe.py init --root <dir>` (``--root`` is a global option and must precede the
subcommand) and a Skill that pointed at a runtime script the installer never ships.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SCRIPTS = ROOT / "runtime" / "scripts"
VIBE = RUNTIME_SCRIPTS / "vibe.py"
DOCUMENT_GLOBS = ("*.md", "docs/**/*.md", "skills/**/*.md", "runtime/opencode/**/*.md")
# `vibe.py` followed (possibly across a `\` line continuation) by a subcommand and,
# later in the same command, `--root`: the global option is in the wrong place.
MISPLACED_ROOT = re.compile(
    r"(?:vibe\.py|\$\{?VIBE\}?(?![A-Za-z_]))\"?(?:[ \t]|\\\n)+(?!--root)([a-z][a-z-]*)[^\n`]*?(?:\\\n[^\n`]*?)*?(?:[ \t]|\\\n)--root\b"
)
RUNTIME_SCRIPT_REFERENCE = re.compile(
    r"(?:\$VIBE_RUNTIME|\$\{VIBE_RUNTIME[^}]*\}|vibe-workflow)/scripts/([A-Za-z0-9_.-]+\.py)"
)


def documents() -> list[Path]:
    found: set[Path] = set()
    for pattern in DOCUMENT_GLOBS:
        found.update(path for path in ROOT.glob(pattern) if path.is_file() and ".git" not in path.parts)
    return sorted(found)


class DocumentedCommandTests(unittest.TestCase):
    def test_root_is_given_before_the_subcommand(self) -> None:
        offenders = []
        for path in documents():
            text = path.read_text(encoding="utf-8")
            for match in MISPLACED_ROOT.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line}: {match.group(0)!r}")
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_cli_rejects_root_after_the_subcommand(self) -> None:
        """Pins the reason for the rule above: argparse only accepts the global form."""
        with tempfile.TemporaryDirectory() as temporary:
            wrong = subprocess.run(
                [sys.executable, str(VIBE), "init", "--root", temporary],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertNotEqual(wrong.returncode, 0)
            self.assertIn("unrecognized arguments: --root", wrong.stdout)
            right = subprocess.run(
                [sys.executable, str(VIBE), "--root", temporary, "init"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(right.returncode, 0, right.stdout)
            self.assertTrue((Path(temporary) / ".project-log").is_dir())

    def test_documented_runtime_scripts_exist(self) -> None:
        missing = []
        for path in documents():
            text = path.read_text(encoding="utf-8")
            for match in RUNTIME_SCRIPT_REFERENCE.finditer(text):
                if not (RUNTIME_SCRIPTS / match.group(1)).is_file():
                    line = text.count("\n", 0, match.start()) + 1
                    missing.append(f"{path.relative_to(ROOT)}:{line}: {match.group(0)}")
        self.assertEqual(missing, [], "\n".join(missing))

    def test_project_init_skill_names_its_installed_script(self) -> None:
        skill = (ROOT / "skills/a-project-init/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("$VIBE_CONFIG/skills/a-project-init/scripts/init_project_agents.py", skill)
        self.assertTrue((ROOT / "skills/a-project-init/scripts/init_project_agents.py").is_file())


if __name__ == "__main__":
    unittest.main()
