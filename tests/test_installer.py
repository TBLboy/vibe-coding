from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/global_installer.py"
BOOTSTRAP = ROOT / "scripts/bootstrap_vibe_python.py"


def run_installer(*arguments: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER), *arguments],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class InstallerTests(unittest.TestCase):
    def test_fresh_install_is_core_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            install = run_installer("install", "--codex-home", str(home), "--skip-preflight")
            self.assertEqual(install.returncode, 0, install.stdout)
            state = json.loads((home / ".vibe-codex-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["optional_mcps"], [])
            self.assertFalse(state["mcp_plugin_installed"])

    def test_selected_codegraph_mcp_is_configured_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "codex-home"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            codegraph = bin_dir / "codegraph"
            codegraph.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            codegraph.chmod(0o700)
            codex = bin_dir / "codex"
            codex.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "state = os.path.join(os.environ['CODEX_HOME'], 'fake-mcp.json')\n"
                "args = sys.argv[1:]\n"
                "if args[:2] == ['mcp', 'get']:\n"
                "    name = args[2]\n"
                "    if not os.path.exists(state): raise SystemExit(1)\n"
                "    data = json.load(open(state))\n"
                "    if data.get('name') != name: raise SystemExit(1)\n"
                "    print('command: ' + data['command'])\n"
                "    print('args: ' + ' '.join(data['args']))\n"
                "    raise SystemExit(0)\n"
                "if args[:2] == ['mcp', 'add']:\n"
                "    name = args[2]; marker = args.index('--')\n"
                "    json.dump({'name': name, 'command': args[marker + 1], 'args': args[marker + 2:]}, open(state, 'w'))\n"
                "    raise SystemExit(0)\n"
                "if args[:2] == ['mcp', 'remove']:\n"
                "    if os.path.exists(state): os.unlink(state)\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(0)\n",
                encoding="utf-8",
            )
            codex.chmod(0o700)
            env = os.environ.copy()
            env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
            install = run_installer(
                "install", "--codex-home", str(home), "--mcp", "codegraph", "--skip-preflight", env=env
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            state = json.loads((home / ".vibe-codex-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["optional_mcps"], ["codegraph"])
            self.assertEqual(state["optional_mcps_owned"], ["codegraph"])
            config_path = home / "config.toml"
            config = config_path.read_text(encoding="utf-8")
            config_path.write_text(
                config.replace(
                    "# VIBE-CODEX-GLOBAL:CONFIG:END",
                    '[mcp_servers.codegraph]\ncommand = "' + str(codegraph) + '"\nargs = ["serve", "--mcp"]\n\n'
                    "# VIBE-CODEX-GLOBAL:CONFIG:END",
                ),
                encoding="utf-8",
            )
            verify = run_installer("verify", "--codex-home", str(home), env=env)
            self.assertEqual(verify.returncode, 0, verify.stdout)
            update = run_installer(
                "update", "--codex-home", str(home), "--without-mcp", "--skip-preflight", env=env
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("[mcp_servers.codegraph]", (home / "config.toml").read_text(encoding="utf-8"))
            state = json.loads((home / ".vibe-codex-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["optional_mcps"], [])

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

    def test_bootstrap_creates_missing_conda_environment(self) -> None:
        if sys.version_info < (3, 11):
            self.skipTest("bootstrap integration requires Python 3.11+")
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "codex-home"
            manager = workspace / "conda"
            created = workspace / "created"
            manager.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                f"created = pathlib.Path({str(created)!r})\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'create':\n"
                "    created.touch()\n"
                "    raise SystemExit(0)\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'run' and created.exists():\n"
                f"    print({str(Path(sys.executable).resolve())!r})\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            manager.chmod(0o700)
            env = os.environ.copy()
            env["CONDA_EXE"] = str(manager)
            env.pop("VIBE_PYTHON", None)
            result = subprocess.run(
                [
                    sys.executable, str(BOOTSTRAP),
                    "--codex-home", str(home),
                    "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                    "--print-python",
                ],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(created.is_file(), result.stdout)
            self.assertEqual((home / "vibe-python").read_text(encoding="utf-8").strip(), str(Path(sys.executable).resolve()))

    def test_global_python_config_pins_hook_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            home.mkdir(parents=True)
            (home / "vibe-python").write_text(sys.executable + "\n", encoding="utf-8")
            install = run_installer(
                "install",
                "--codex-home",
                str(home),
                "--without-mcp",
                "--skip-preflight",
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            config = (home / "config.toml").read_text(encoding="utf-8")
            parsed = tomllib.loads(config)
            command = parsed["hooks"]["SessionStart"][0]["hooks"][0]["command"]
            self.assertTrue(command.startswith(f'\"{Path(sys.executable).resolve()}\" '), command)
            self.assertNotEqual(command.split(maxsplit=1)[0], "python3")

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
            self.assertEqual(state["package_version"], "0.4.1")
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
