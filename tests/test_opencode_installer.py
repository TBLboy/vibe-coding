"""TASK-073: OpenCode install, update, verify, and uninstall lifecycle."""
from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/opencode_installer.py"
INSTALL_SH = ROOT / "runtime" / "opencode" / "install.sh"


def load_installer_module():
    spec = importlib.util.spec_from_file_location("opencode_installer_under_test", INSTALLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_installer(*arguments: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER), *arguments],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class OpenCodeInstallerTests(unittest.TestCase):
    def install(self, home: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return run_installer(
            "install",
            "--opencode-home",
            str(home),
            "--skip-preflight",
            "--skip-plugin-install",
            *extra,
        )

    def test_fresh_install_verify_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            project_log = Path(temporary) / ".project-log"
            project_log.mkdir()
            (project_log / "keep.txt").write_text("keep\n", encoding="utf-8")

            install = self.install(home)
            self.assertEqual(install.returncode, 0, install.stdout)
            self.assertTrue((home / "AGENTS.md").is_file())
            self.assertTrue((home / "agents/vibe-main.md").is_file())
            self.assertTrue((home / "commands/vibe-start.md").is_file())
            self.assertTrue((home / "plugins/vibe-workflow.ts").is_file())
            self.assertTrue((home / "skills/a-loop-control/SKILL.md").is_file())
            self.assertTrue((home / "vibe-workflow/scripts/vibe.py").is_file())
            self.assertTrue((home / "vibe-python").is_file())
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["default_agent"], "vibe-main")
            self.assertIn("./plugins/vibe-workflow.ts", config["plugin"])
            state = json.loads((home / ".vibe-opencode-installation-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["plugin_install"], "skipped")
            self.assertIn("vibe-workflow/scripts/vibe.py", state["managed_files"])

            verify = run_installer("verify", "--opencode-home", str(home))
            self.assertEqual(verify.returncode, 0, verify.stdout)

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())
            self.assertFalse((home / "plugins/vibe-workflow.ts").exists())
            self.assertFalse((home / "vibe-workflow/scripts/vibe.py").exists())
            self.assertTrue((project_log / "keep.txt").is_file())

    def test_install_is_idempotent_and_preserves_user_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            original = {
                "$schema": "https://opencode.ai/config.json",
                "plugin": ["user-plugin"],
                "default_agent": "user-agent",
                "mcp": {"user": {"type": "remote", "url": "https://example.invalid/mcp"}},
            }
            (home / "opencode.json").write_text(json.dumps(original, indent=2), encoding="utf-8")

            first = self.install(home)
            self.assertEqual(first.returncode, 0, first.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertIn("user-plugin", config["plugin"])
            self.assertIn("./plugins/vibe-workflow.ts", config["plugin"])
            self.assertEqual(config["mcp"], original["mcp"])
            self.assertEqual(config["default_agent"], "vibe-main")

            second = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight", "--skip-plugin-install",
            )
            self.assertEqual(second.returncode, 0, second.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["plugin"].count("./plugins/vibe-workflow.ts"), 1)
            self.assertIn("user-plugin", config["plugin"])

    def test_repeated_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            first = self.install(home)
            self.assertEqual(first.returncode, 0, first.stdout)
            before = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            state_before = json.loads(
                (home / ".vibe-opencode-installation-state.json").read_text(encoding="utf-8")
            )

            second = self.install(home)
            self.assertEqual(second.returncode, 0, second.stdout)
            after = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(after["plugin"], before["plugin"])
            self.assertEqual(after["plugin"].count("./plugins/vibe-workflow.ts"), 1)
            state_after = json.loads(
                (home / ".vibe-opencode-installation-state.json").read_text(encoding="utf-8")
            )
            # installed_at is stable across reinstalls; updated_at advances.
            self.assertEqual(state_after["installed_at"], state_before["installed_at"])
            self.assertEqual(state_after["managed_files"], state_before["managed_files"])

    def test_uninstall_keeps_project_log_inside_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            project_log = home / ".project-log"
            project_log.mkdir()
            (project_log / "ledger.txt").write_text("ledger\n", encoding="utf-8")

            self.assertEqual(self.install(home).returncode, 0)
            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertTrue((project_log / "ledger.txt").is_file())
            self.assertEqual(
                (project_log / "ledger.txt").read_text(encoding="utf-8"), "ledger\n"
            )
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())

    def test_user_edit_to_installed_config_survives_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["plugin"].append("another-user-plugin")
            config["model"] = "user/model"
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight", "--skip-plugin-install",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("another-user-plugin", updated["plugin"])
            self.assertIn("./plugins/vibe-workflow.ts", updated["plugin"])
            self.assertEqual(updated["model"], "user/model")

    def test_local_skill_modification_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            skill = home / "skills/a-loop-control/SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal change\n", encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight", "--skip-plugin-install",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("PRESERVED local modification", update.stdout)
            self.assertIn("local change", skill.read_text(encoding="utf-8"))
            state = json.loads((home / ".vibe-opencode-installation-state.json").read_text(encoding="utf-8"))
            self.assertIn("skills/a-loop-control/SKILL.md", state["preserved_local"])

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertTrue(skill.is_file())
            self.assertIn("local change", skill.read_text(encoding="utf-8"))

    def test_plugin_dependency_install_uses_package_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            fake_npm = bin_dir / "npm"
            fake_npm.write_text(
                "#!/usr/bin/env python3\n"
                "import json, pathlib, sys\n"
                "cwd = pathlib.Path.cwd()\n"
                "package = json.loads((cwd / 'package.json').read_text())\n"
                "assert package['dependencies']['@opencode-ai/plugin'] == '1.18.4'\n"
                "target = cwd / 'node_modules/@opencode-ai/plugin'\n"
                "target.mkdir(parents=True, exist_ok=True)\n"
                "(target / 'package.json').write_text('{\"version\": \"1.18.4\"}')\n"
                "print('installed')\n",
                encoding="utf-8",
            )
            fake_npm.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]

            install = run_installer(
                "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            if install.returncode != 0 and "npm or bun is required" in install.stdout:
                self.skipTest("no runnable npm/bun interpreter available")
            self.assertEqual(install.returncode, 0, install.stdout)
            self.assertTrue((home / "node_modules/@opencode-ai/plugin").is_dir())
            verify = run_installer(
                "verify", "--opencode-home", str(home), env=environment,
            )
            self.assertEqual(verify.returncode, 0, verify.stdout)

    def test_uninstall_preserves_user_plugin_and_permission_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            (home / "opencode.json").write_text(
                json.dumps({"plugin": ["user-plugin"], "model": "user/model"}, indent=2),
                encoding="utf-8",
            )
            self.assertEqual(self.install(home).returncode, 0)
            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["plugin"], ["user-plugin"])
            self.assertEqual(config["model"], "user/model")
            self.assertNotIn("default_agent", config)

    def test_pre_existing_asset_conflict_aborts_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            skill = home / "skills/a-loop-control/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("user original\n", encoding="utf-8")

            install = self.install(home)
            self.assertNotEqual(install.returncode, 0)
            self.assertIn("pre-existing file differs from package", install.stdout)
            self.assertIn("Nothing was written", install.stdout)
            self.assertEqual(skill.read_text(encoding="utf-8"), "user original\n")
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())
            self.assertFalse((home / "opencode.json").exists())

    def test_runtime_local_modification_is_preserved_on_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            runtime_file = home / "vibe-workflow/scripts/vibe.py"
            runtime_file.write_text(
                runtime_file.read_text(encoding="utf-8") + "\n# local runtime change\n",
                encoding="utf-8",
            )

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight", "--skip-plugin-install",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("PRESERVED local modification", update.stdout)
            self.assertIn("vibe-workflow/scripts/vibe.py", update.stdout)
            self.assertIn("local runtime change", runtime_file.read_text(encoding="utf-8"))
            state = json.loads((home / ".vibe-opencode-installation-state.json").read_text(encoding="utf-8"))
            self.assertIn("vibe-workflow/scripts/vibe.py", state["preserved_local"])

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertTrue(runtime_file.is_file())

    def test_pre_existing_managed_config_values_survive_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            (home / "opencode.json").write_text(
                json.dumps(
                    {"default_agent": "vibe-main", "permission": {"skill": {"*": "allow"}}},
                    indent=2,
                ),
                encoding="utf-8",
            )
            self.assertEqual(self.install(home).returncode, 0)
            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["default_agent"], "vibe-main")
            self.assertEqual(config["permission"]["skill"]["*"], "allow")

    def test_array_plugin_entry_is_preserved_and_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            array_plugin = ["some-plugin", {"enabled": True}]
            (home / "opencode.json").write_text(
                json.dumps({"plugin": [array_plugin]}, indent=2), encoding="utf-8"
            )
            install = self.install(home)
            self.assertEqual(install.returncode, 0, install.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertIn(array_plugin, config["plugin"])
            self.assertEqual(config["plugin"].count("./plugins/vibe-workflow.ts"), 1)

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["plugin"], [array_plugin])

    def test_uninstall_restores_created_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            fake_npm = bin_dir / "npm"
            fake_npm.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib\n"
                "cwd = pathlib.Path.cwd()\n"
                "target = cwd / 'node_modules/@opencode-ai/plugin'\n"
                "target.mkdir(parents=True, exist_ok=True)\n"
                "(target / 'package.json').write_text('{\"version\": \"1.18.4\"}')\n",
                encoding="utf-8",
            )
            fake_npm.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]

            install = run_installer(
                "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            self.assertTrue((home / "package.json").is_file())

            uninstall = run_installer(
                "uninstall", "--opencode-home", str(home), env=environment,
            )
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertFalse((home / "package.json").exists())

    def test_bun_install_omits_npm_only_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            record = workspace / "bun-args.txt"
            fake_bun = bin_dir / "bun"
            fake_bun.write_text(
                f"#!{sys.executable}\n"
                "import pathlib, sys\n"
                f"pathlib.Path({str(record)!r}).write_text(' '.join(sys.argv[1:]))\n"
                "cwd = pathlib.Path.cwd()\n"
                "target = cwd / 'node_modules/@opencode-ai/plugin'\n"
                "target.mkdir(parents=True, exist_ok=True)\n"
                "(target / 'package.json').write_text('{\"version\": \"1.18.4\"}')\n",
                encoding="utf-8",
            )
            fake_bun.chmod(0o700)
            environment = os.environ.copy()
            # Restrict PATH so only the fake bun is discoverable as a package manager.
            environment["PATH"] = str(bin_dir)

            install = run_installer(
                "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            self.assertEqual(record.read_text(encoding="utf-8"), "install")

    def test_install_sh_defaults_to_install_with_options_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            result = subprocess.run(
                ["bash", str(INSTALL_SH), "--opencode-home", str(home),
                 "--skip-preflight", "--skip-plugin-install"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((home / "opencode.json").is_file())
            self.assertTrue((home / "AGENTS.md").is_file())

    def test_user_permission_edit_is_not_reset_by_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["permission"]["skill"]["*"] = "ask"
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight", "--skip-plugin-install",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["permission"]["skill"]["*"], "ask")

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            final = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(final["permission"]["skill"]["*"], "ask")

    def test_package_permission_action_change_updates_ownership(self) -> None:
        module = load_installer_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package"
            surface = root / "runtime/opencode"
            surface.mkdir(parents=True)
            config_path = surface / "opencode.json"
            home = Path(temporary) / "home"
            home.mkdir()

            def write_source(action: str) -> None:
                config_path.write_text(
                    json.dumps({"default_agent": "vibe-main", "permission": {"skill": {"*": action}}}),
                    encoding="utf-8",
                )

            write_source("allow")
            first = module.merge_config(home, root, {})
            self.assertEqual(first["permissions_added"]["skill"]["*"]["installed"], "allow")

            write_source("deny")
            second = module.merge_config(home, root, first)
            self.assertEqual(second["permissions_added"]["skill"]["*"]["installed"], "deny")
            merged = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(merged["permission"]["skill"]["*"], "deny")

            module.remove_managed_config(home, second)
            # The installer created this config and owned every key in it, so it is removed.
            self.assertFalse((home / "opencode.json").exists())

    def test_damaged_agents_block_refuses_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            agents = home / "AGENTS.md"
            text = agents.read_text(encoding="utf-8").replace("<!-- VIBE-OPENCODE-GLOBAL:END -->", "")
            agents.write_text(text + "\nUSER CONTENT AFTER BLOCK\n", encoding="utf-8")

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertNotEqual(uninstall.returncode, 0)
            self.assertIn("damaged managed block", uninstall.stdout)
            self.assertTrue(agents.is_file())
            self.assertIn("USER CONTENT AFTER BLOCK", agents.read_text(encoding="utf-8"))
            self.assertTrue((home / "plugins/vibe-workflow.ts").is_file())
            self.assertTrue((home / ".vibe-opencode-installation-state.json").is_file())

    def test_package_manager_failure_rolls_back_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            fake_npm = bin_dir / "npm"
            fake_npm.write_text("#!/bin/sh\necho 'boom' >&2\nexit 1\n", encoding="utf-8")
            fake_npm.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]

            install = run_installer(
                "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            self.assertNotEqual(install.returncode, 0)
            self.assertFalse((home / "plugins/vibe-workflow.ts").exists())
            self.assertFalse((home / "vibe-workflow/scripts/vibe.py").exists())
            self.assertFalse((home / "AGENTS.md").exists())
            self.assertFalse((home / "opencode.json").exists())
            self.assertFalse((home / "package.json").exists())
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())

    def test_corrupt_package_json_blocks_uninstall_before_deleting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            fake_npm = bin_dir / "npm"
            fake_npm.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib\n"
                "cwd = pathlib.Path.cwd()\n"
                "target = cwd / 'node_modules/@opencode-ai/plugin'\n"
                "target.mkdir(parents=True, exist_ok=True)\n"
                "(target / 'package.json').write_text('{\"version\": \"1.18.4\"}')\n",
                encoding="utf-8",
            )
            fake_npm.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]
            self.assertEqual(
                run_installer(
                    "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
                ).returncode,
                0,
            )
            (home / "package.json").write_text("{ not json", encoding="utf-8")

            uninstall = run_installer("uninstall", "--opencode-home", str(home), env=environment)
            self.assertNotEqual(uninstall.returncode, 0)
            self.assertTrue((home / "plugins/vibe-workflow.ts").is_file())
            self.assertTrue((home / ".vibe-opencode-installation-state.json").is_file())
            self.assertTrue((home / "AGENTS.md").is_file())

    def test_vibe_python_local_modification_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            pointer = home / "vibe-python"
            pointer.write_text("/custom/python\n", encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight", "--skip-plugin-install",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("PRESERVED local modification", update.stdout)
            self.assertEqual(pointer.read_text(encoding="utf-8"), "/custom/python\n")

    def test_package_removed_permission_rule_is_cleaned_up(self) -> None:
        module = load_installer_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package"
            surface = root / "runtime/opencode"
            surface.mkdir(parents=True)
            config_path = surface / "opencode.json"
            home = Path(temporary) / "home"
            home.mkdir()
            # The package ships a rule; the user config starts empty so the installer owns it.
            config_path.write_text(
                json.dumps({"default_agent": "vibe-main", "permission": {"skill": {"*": "allow"}}}),
                encoding="utf-8",
            )
            first = module.merge_config(home, root, {})
            self.assertIn("skill", first["permissions_added"])
            self.assertFalse(first["permissions_added"]["skill"]["*"]["present"])

            # The next package version ships no permission rules at all.
            config_path.write_text(json.dumps({"default_agent": "vibe-main"}), encoding="utf-8")
            second = module.merge_config(home, root, first)
            merged = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertNotIn("permission", merged)
            self.assertNotIn("skill", second["permissions_added"])

    def test_user_deleted_managed_permission_rule_is_not_restored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            del config["permission"]["skill"]["*"]
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight", "--skip-plugin-install",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("managed rule removed by the user", update.stdout)
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("*", (updated.get("permission") or {}).get("skill") or {})

    def test_package_manager_failure_leaves_no_artifacts_or_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            fake_npm = bin_dir / "npm"
            fake_npm.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "cwd = pathlib.Path.cwd()\n"
                "(cwd / 'node_modules').mkdir(exist_ok=True)\n"
                "(cwd / 'package-lock.json').write_text('{}')\n"
                "print('boom', file=sys.stderr)\n"
                "sys.exit(1)\n",
                encoding="utf-8",
            )
            fake_npm.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]

            install = run_installer(
                "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            self.assertNotEqual(install.returncode, 0)
            self.assertFalse((home / "node_modules").exists())
            self.assertFalse((home / "package-lock.json").exists())
            for name in ("agents", "commands", "plugins", "skills", "vibe-workflow"):
                self.assertFalse((home / name).exists(), f"{name} should not be left behind")
            self.assertFalse((home / "AGENTS.md").exists())
            self.assertFalse((home / "opencode.json").exists())

    def test_uninstall_keeps_user_created_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            user_dir = home / "skills/user-empty"
            user_dir.mkdir()

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertTrue(user_dir.is_dir())
            self.assertFalse((home / "skills/a-loop-control").exists())

    def test_malformed_created_dirs_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            state_path = home / ".vibe-opencode-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["created_dirs"] = "skills"
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertNotEqual(uninstall.returncode, 0)
            self.assertIn("created_dirs", uninstall.stdout)
            self.assertTrue((home / "plugins/vibe-workflow.ts").is_file())

    def test_state_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            victim = workspace / "outside.txt"
            victim.write_text("do not delete me\n", encoding="utf-8")
            import hashlib

            digest = hashlib.sha256(victim.read_bytes()).hexdigest()
            state_path = home / ".vibe-opencode-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["managed_files"]["../outside.txt"] = digest
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertNotEqual(uninstall.returncode, 0)
            self.assertIn("unsafe", uninstall.stdout)
            self.assertTrue(victim.is_file())
            self.assertEqual(victim.read_text(encoding="utf-8"), "do not delete me\n")
            self.assertTrue((home / "plugins/vibe-workflow.ts").is_file())

    def test_absolute_created_dir_in_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            outside_dir = workspace / "outside-dir"
            outside_dir.mkdir()
            state_path = home / ".vibe-opencode-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["created_dirs"] = [str(outside_dir)]
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertNotEqual(uninstall.returncode, 0)
            self.assertIn("unsafe", uninstall.stdout)
            self.assertTrue(outside_dir.is_dir())
            self.assertTrue((home / "plugins/vibe-workflow.ts").is_file())

    def test_existing_lockfile_is_restored_after_failed_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            flag = workspace / "fail"
            fake_npm = bin_dir / "npm"
            fake_npm.write_text(
                f"#!{sys.executable}\n"
                "import pathlib, sys\n"
                f"if pathlib.Path({str(flag)!r}).exists():\n"
                "    cwd = pathlib.Path.cwd()\n"
                "    (cwd / 'package-lock.json').write_text('{\"changed\": true}')\n"
                "    sys.exit(1)\n"
                "cwd = pathlib.Path.cwd()\n"
                "(cwd / 'package-lock.json').write_text('{\"original\": true}')\n"
                "t = cwd / 'node_modules/@opencode-ai/plugin'\n"
                "t.mkdir(parents=True, exist_ok=True)\n"
                "(t / 'package.json').write_text('{\"version\": \"1.18.4\"}')\n",
                encoding="utf-8",
            )
            fake_npm.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]

            self.assertEqual(
                run_installer(
                    "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
                ).returncode,
                0,
            )
            lockfile = home / "package-lock.json"
            original = lockfile.read_text(encoding="utf-8")
            flag.write_text("fail")

            update = run_installer(
                "update", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            self.assertNotEqual(update.returncode, 0)
            self.assertEqual(lockfile.read_text(encoding="utf-8"), original)
            self.assertTrue((home / "plugins/vibe-workflow.ts").is_file())

    def test_user_edited_schema_survives_update_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["$schema"] = "https://user.example/schema.json"
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight", "--skip-plugin-install",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertEqual(
                json.loads(config_path.read_text(encoding="utf-8"))["$schema"],
                "https://user.example/schema.json",
            )

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertTrue(config_path.is_file())
            self.assertEqual(
                json.loads(config_path.read_text(encoding="utf-8"))["$schema"],
                "https://user.example/schema.json",
            )

    def test_symlink_escaping_home_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            outside = workspace / "outside"
            outside.mkdir()
            home.mkdir()
            os.symlink(outside, home / "plugins")

            install = self.install(home)
            self.assertNotEqual(install.returncode, 0)
            self.assertIn("outside the OpenCode home", install.stdout)
            self.assertFalse((outside / "vibe-workflow.ts").exists())
            self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_special_files_are_refused(self) -> None:
        for name, initial in (
            ("AGENTS.md", "user rules\n"),
            ("opencode.json", "{}\n"),
            ("package.json", "{}\n"),
            ("vibe-python", "/usr/bin/python3\n"),
            (".vibe-opencode-installation-state.json", "{}\n"),
            ("package-lock.json", "{}\n"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                workspace = Path(temporary)
                home = workspace / "opencode"
                outside = workspace / "outside.txt"
                outside.write_text(initial, encoding="utf-8")
                home.mkdir()
                os.symlink(outside, home / name)

                install = self.install(home)
                self.assertNotEqual(install.returncode, 0)
                self.assertIn("outside the OpenCode home", install.stdout)
                self.assertEqual(outside.read_text(encoding="utf-8"), initial)

    def test_symlinked_node_modules_is_refused_before_package_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            outside = workspace / "outside"
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            outside.mkdir()
            home.mkdir()
            os.symlink(outside, home / "node_modules")
            fake_npm = bin_dir / "npm"
            fake_npm.write_text(
                f"#!{sys.executable}\n"
                "import pathlib\n"
                "cwd = pathlib.Path.cwd()\n"
                "t = cwd / 'node_modules/@opencode-ai/plugin'\n"
                "t.mkdir(parents=True, exist_ok=True)\n"
                "(t / 'package.json').write_text('{\"version\": \"1.18.4\"}')\n",
                encoding="utf-8",
            )
            fake_npm.chmod(0o700)
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]

            install = run_installer(
                "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            self.assertNotEqual(install.returncode, 0)
            self.assertIn("outside the OpenCode home", install.stdout)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())

    def test_symlinked_backup_directory_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            outside = workspace / "outside"
            home.mkdir()
            outside.mkdir()
            os.symlink(outside, home / "backups")

            install = self.install(home)
            self.assertNotEqual(install.returncode, 0)
            self.assertIn("outside the OpenCode home", install.stdout)
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
