from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/global_installer.py"


def run_installer(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class InstallerTests(unittest.TestCase):
    def test_fresh_install_verify_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            install = run_installer(
                "install",
                "--codex-home",
                str(home),
                "--without-mcp",
                "--skip-preflight",
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            self.assertTrue((home / "vibe-workflow/scripts/loopctl.py").is_file())
            self.assertIn("VIBE-CODEX-GLOBAL:CONFIG:BEGIN", (home / "config.toml").read_text(encoding="utf-8"))

            verify = run_installer("verify", "--codex-home", str(home), "--without-mcp")
            self.assertEqual(verify.returncode, 0, verify.stdout)

            uninstall = run_installer("uninstall", "--codex-home", str(home), "--without-mcp")
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertFalse((home / ".vibe-codex-installation-state.json").exists())
            self.assertFalse((home / "vibe-workflow/scripts/loopctl.py").exists())

    def test_local_modification_is_preserved_when_package_file_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            install = run_installer(
                "install",
                "--codex-home",
                str(home),
                "--without-mcp",
                "--skip-preflight",
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            target = home / "skills/a-loop-control/SKILL.md"
            target.write_text(target.read_text(encoding="utf-8") + "\nlocal change\n", encoding="utf-8")
            update = run_installer(
                "update",
                "--codex-home",
                str(home),
                "--without-mcp",
                "--skip-preflight",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("PRESERVED local modification", update.stdout)
            self.assertIn("local change", target.read_text(encoding="utf-8"))

    def test_upgrade_from_legacy_030_install(self) -> None:
        archive = ROOT / "dist/vibe-coding-codex-global-core-0.3.0.zip"
        if not archive.is_file():
            self.skipTest("legacy 0.3.0 archive is available only in the source release workspace")
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            with zipfile.ZipFile(archive) as package:
                package.extractall(workspace / "old")
            old_root = workspace / "old/codex-vibe-global-core"
            home = workspace / "codex-home"
            old = subprocess.run(
                [
                    sys.executable,
                    str(old_root / "scripts/global_installer.py"),
                    "install",
                    "--codex-home",
                    str(home),
                    "--without-mcp",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )
            self.assertEqual(old.returncode, 0, old.stdout)
            self.assertTrue((home / "vibe-workflow/installation-state.json").is_file())

            update = run_installer(
                "update",
                "--codex-home",
                str(home),
                "--without-mcp",
                "--skip-preflight",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            state = json.loads((home / ".vibe-codex-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["package_version"], "0.4.0")
            self.assertTrue((home / "vibe-workflow/scripts/loopctl.py").is_file())

    def test_without_hooks_can_still_set_access_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            install = run_installer(
                "install",
                "--codex-home",
                str(home),
                "--without-mcp",
                "--without-hooks",
                "--access-profile",
                "workspace",
                "--skip-preflight",
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            config = (home / "config.toml").read_text(encoding="utf-8")
            self.assertIn('sandbox_mode = "workspace-write"', config)
            self.assertNotIn("[[hooks.", config)


if __name__ == "__main__":
    unittest.main()
