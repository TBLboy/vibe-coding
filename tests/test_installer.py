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


def write_test_executable(directory: Path, name: str, python_source: str) -> Path:
    if os.name != "nt":
        path = directory / name
        path.write_text("#!/usr/bin/env python3\n" + python_source, encoding="utf-8")
        path.chmod(0o700)
        return path

    script = directory / f"{name}.py"
    script.write_text(python_source, encoding="utf-8")
    path = directory / f"{name}.cmd"
    path.write_text(
        "@echo off\n"
        f'"{sys.executable}" "%~dp0{name}.py" %*\n',
        encoding="utf-8",
    )
    return path


class InstallerTests(unittest.TestCase):
    def test_fresh_install_is_core_only_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            install = run_installer("install", "--codex-home", str(home), "--skip-preflight")
            self.assertEqual(install.returncode, 0, install.stdout)
            state = json.loads((home / ".vibe-codex-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["optional_mcps"], [])
            self.assertFalse(state["mcp_plugin_installed"])

    def test_selected_vibe_toolbelt_plugin_is_installed_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "codex-home"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            codex = write_test_executable(
                bin_dir,
                "codex",
                "import os, sys\n"
                "state = os.path.join(os.environ['CODEX_HOME'], 'fake-plugin-installed')\n"
                "args = sys.argv[1:]\n"
                "if args[:3] == ['plugin', 'marketplace', 'add']:\n"
                "    raise SystemExit(0)\n"
                "if args[:2] == ['plugin', 'add']:\n"
                "    open(state, 'w').close()\n"
                "    raise SystemExit(0)\n"
                "if args[:2] == ['plugin', 'list']:\n"
                "    if os.path.exists(state):\n"
                "        print('vibe-toolbelt@vibe-global-toolbox installed, enabled 0.4.1')\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(0)\n",
            )
            env = os.environ.copy()
            env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
            install = run_installer(
                "install", "--codex-home", str(home), "--mcp", "vibe-toolbelt", "--skip-preflight", env=env
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            state = json.loads((home / ".vibe-codex-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["optional_mcps"], ["vibe-toolbelt"])
            self.assertEqual(state["optional_mcps_owned"], ["vibe-toolbelt"])
            self.assertTrue(state["mcp_plugin_installed"])

    def test_selected_codegraph_mcp_is_configured_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "codex-home"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            codegraph = write_test_executable(bin_dir, "codegraph", "raise SystemExit(0)\n")
            codex = write_test_executable(
                bin_dir,
                "codex",
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
            )
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
                    '[mcp_servers.codegraph]\ncommand = "' + codegraph.as_posix() + '"\nargs = ["serve", "--mcp"]\n\n'
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
            created = workspace / "created"
            manager = write_test_executable(
                workspace,
                "conda",
                "import pathlib, sys\n"
                f"created = pathlib.Path({str(created)!r})\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'create':\n"
                "    created.touch()\n"
                "    raise SystemExit(0)\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'run' and created.exists():\n"
                f"    print({str(Path(sys.executable).resolve())!r})\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(1)\n",
            )
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
            session_hook = parsed["hooks"]["SessionStart"][0]["hooks"][0]
            command = session_hook["command"]
            command_windows = session_hook["commandWindows"]
            expected_unix_python = Path(sys.executable).resolve().as_posix()
            expected_windows_python = str(Path(sys.executable).resolve())
            self.assertTrue(command.startswith(f'\"{expected_unix_python}\" '), command)
            self.assertTrue(command_windows.startswith(f'\"{expected_windows_python}\" '), command_windows)
            self.assertNotEqual(command.split(maxsplit=1)[0], "python3")
            self.assertNotEqual(command_windows.split(maxsplit=1)[0], "python3")

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

    def test_update_repairs_cc_switch_rewritten_config(self) -> None:
        # cc-switch rewrites config.toml on model hot-switch: it keeps the
        # BEGIN marker but drops the END marker, interleaves its own
        # [model_providers] tables with the managed hooks block, and drops
        # marketplaces/plugins. An update must repair the block without losing
        # the model provider or MCP configuration.
        cc_switch_config = (
            'model_provider = "custom"\n'
            'model = "deepseek-v4-flash-free"\n'
            'model_catalog_json = "cc-switch-model-catalog.json"\n'
            "\n"
            "[features]\n"
            "goals = true\n"
            "\n"
            "# VIBE-CODEX-GLOBAL:CONFIG:BEGIN\n"
            "[[hooks.SessionStart]]\n"
            "[[hooks.SessionStart.hooks]]\n"
            'type = "command"\n'
            'command = "echo hi"\n'
            "\n"
            "[model_providers]\n"
            "[[hooks.PostToolUse]]\n"
            "[model_providers.custom]\n"
            'name = "custom"\n'
            'base_url = "http://127.0.0.1:15721/v1"\n'
            "[[hooks.PostToolUse.hooks]]\n"
            'type = "command"\n'
            'command = "echo bye"\n'
            "\n"
            "[mcp_servers.codegraph]\n"
            'command = "npx"\n'
            'args = ["serve", "--mcp"]\n'
            "\n"
            "[marketplaces.vibe-global-toolbox]\n"
            'source_type = "local"\n'
            "source = 'D:\\\\Project\\\\vibe-coding'\n"
            "\n"
            '[plugins."vibe-toolbelt@vibe-global-toolbox"]\n'
            "enabled = true\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            home.mkdir()
            (home / "config.toml").write_text(cc_switch_config, encoding="utf-8")

            update = run_installer(
                "update",
                "--codex-home",
                str(home),
                "--access-profile",
                "keep-existing",
                "--skip-preflight",
            )
            self.assertEqual(update.returncode, 0, update.stdout)

            raw = (home / "config.toml").read_text(encoding="utf-8")
            parsed = tomllib.loads(raw)
            self.assertEqual(parsed["model_providers"]["custom"]["base_url"], "http://127.0.0.1:15721/v1")
            self.assertEqual(parsed["mcp_servers"]["codegraph"]["command"], "npx")
            self.assertIn("SessionStart", parsed["hooks"])
            self.assertIn("# VIBE-CODEX-GLOBAL:CONFIG:BEGIN", raw)
            self.assertIn("# VIBE-CODEX-GLOBAL:CONFIG:END", raw)

    def test_uninstall_preserves_cc_switch_provider_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "codex-home"
            install = run_installer(
                "install",
                "--codex-home",
                str(home),
                "--skip-preflight",
            )
            self.assertEqual(install.returncode, 0, install.stdout)

            # Simulate cc-switch rewriting the installed config (no END marker,
            # model_providers/mcp_servers interleaved inside the managed block).
            rewritten = (
                'model_provider = "custom"\n'
                "model = \"gpt-5.4\"\n"
                "model_catalog_json = \"cc-switch-model-catalog.json\"\n"
                "\n"
                "# VIBE-CODEX-GLOBAL:CONFIG:BEGIN\n"
                "[[hooks.SessionStart]]\n"
                "[model_providers]\n"
                "[model_providers.custom]\n"
                'name = "custom"\n'
                'base_url = "http://127.0.0.1:15721/v1"\n'
                "[mcp_servers.codegraph]\n"
                'command = "npx"\n'
                'args = ["serve", "--mcp"]\n'
            )
            (home / "config.toml").write_text(rewritten, encoding="utf-8")

            uninstall = run_installer(
                "uninstall",
                "--codex-home",
                str(home),
                "--skip-preflight",
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)

            raw = (home / "config.toml").read_text(encoding="utf-8")
            self.assertNotIn("VIBE-CODEX-GLOBAL", raw)
            parsed = tomllib.loads(raw)
            self.assertEqual(parsed["model_providers"]["custom"]["base_url"], "http://127.0.0.1:15721/v1")
            self.assertEqual(parsed["mcp_servers"]["codegraph"]["command"], "npx")


if __name__ == "__main__":
    unittest.main()
