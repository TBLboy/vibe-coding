"""Isolated acceptance tests for the V2 installer without external packages."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import shutil
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("v2installer", ROOT / "scripts" / "vibe_v2_installer.py")
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


RETIRED_SKILLS = ['a-project-archive', 'b-multi-role-ux-audit', 'b-concise-communication', 'b-plan-stress-test', 'b-jetson-robot-policy-deployment', 'b-opencode-model-config']


class InstallerTests(unittest.TestCase):
    def test_install_verify_and_uninstall_preserve_user_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            original = {
                "model": "custom/example",
                "provider": {"custom": {"options": {"apiKey": "not-printed"}}},
                "mcp": {"private": {"type": "remote", "url": "https://example.invalid/mcp"}},
                "plugin": ["user-plugin"],
            }
            (home / "opencode.json").write_text(json.dumps(original), encoding="utf-8")
            installer.install(ROOT, home)
            installed = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(installed["model"], original["model"])
            self.assertEqual(installed["provider"], original["provider"])
            self.assertEqual(installed["mcp"], original["mcp"])
            self.assertIn("user-plugin", installed["plugin"])
            self.assertIn(installer.PLUGIN_SPEC, installed["plugin"])
            self.assertEqual(installed["default_agent"], "vibe-main")
            self.assertTrue((home / "skills" / "a-verification" / "SKILL.md").is_file())
            self.assertEqual((home / "skills" / "b-web-research-tooling" / "SKILL.md").read_bytes(),
                             (ROOT / "skills" / "b-web-research-tooling" / "SKILL.md").read_bytes())
            self.assertEqual(len(list((home / "skills").glob("*/SKILL.md"))), 22)
            for retired in RETIRED_SKILLS:
                self.assertFalse((home / "skills" / retired).exists(), retired)
            for skill, reference in [
                ("a-architecture-decision", "decision-method.md"),
                ("a-engineering-landing", "change-method.md"),
                ("a-verification", "test-design.md"),
            ]:
                relative = Path("skills") / skill / "references" / reference
                self.assertEqual((home / relative).read_bytes(), (ROOT / relative).read_bytes())
            ui_root = Path("skills/b-ui-design")
            ui_files = [path.relative_to(ROOT) for path in (ROOT / ui_root).rglob("*") if path.is_file()]
            self.assertGreater(len(ui_files), 20)
            for relative in ui_files:
                self.assertEqual((home / relative).read_bytes(), (ROOT / relative).read_bytes(), str(relative))
            self.assertEqual(
                [path.relative_to(home / ui_root).as_posix() for path in (home / ui_root).rglob("SKILL.md")],
                ["SKILL.md"],
            )
            installer.verify(ROOT, home)
            installer.uninstall(home)
            restored = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(restored, original)
            self.assertFalse((home / installer.STATE_FILE).exists())
            self.assertFalse((home / "skills" / "a-verification" / "SKILL.md").exists())
            self.assertFalse(any(path.is_file() for path in (home / ui_root).rglob("*")))

    def test_uninstall_preserves_modified_managed_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            installer.install(ROOT, home)
            changed = home / "agents" / "vibe-main.md"
            changed.write_text("user change", encoding="utf-8")
            installer.uninstall(home)
            self.assertTrue(changed.exists())

    def test_repeated_install_keeps_original_config_ownership_for_uninstall(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            original = {"plugin": ["user-plugin"], "model": "custom/example"}
            (home / "opencode.json").write_text(json.dumps(original), encoding="utf-8")
            installer.install(ROOT, home)
            installer.install(ROOT, home)
            installer.uninstall(home)
            restored = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(restored, original)

    def test_install_refuses_unowned_or_modified_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            agent = home / "agents" / "vibe-main.md"
            agent.parent.mkdir(parents=True)
            agent.write_text("user original", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unowned or user-modified"):
                installer.install(ROOT, home)
            self.assertEqual(agent.read_text(), "user original")
            agent.unlink()
            installer.install(ROOT, home)
            self.assertTrue((home / "docs" / "03-STATE-MACHINE.md").is_file())
            self.assertTrue((home / "schemas" / "task.schema.json").is_file())
            agent.write_text("user edited", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unowned or user-modified"):
                installer.install(ROOT, home)
            self.assertEqual(agent.read_text(), "user edited")

    def test_uninstall_preserves_user_changed_default_agent(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            installer.install(ROOT, home)
            path = home / "opencode.json"
            config = json.loads(path.read_text())
            config["default_agent"] = "my-agent"
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(RuntimeError, "default_agent"):
                installer.install(ROOT, home)
            installer.uninstall(home)
            self.assertEqual(json.loads(path.read_text())["default_agent"], "my-agent")

    def test_install_skips_python_bytecode_caches(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            (source / "docs").mkdir(parents=True)
            (source / "schemas").mkdir(parents=True)
            (source / "shared" / "team-contracts").mkdir(parents=True)
            (source / "runtime" / "core").mkdir(parents=True)
            (source / "runtime" / "core" / "mode.ts").write_text("export {};\n", encoding="utf-8")
            plugin = source / "runtime" / "opencode" / "plugins" / "vibe-v2"
            plugin.mkdir(parents=True)
            (plugin / "index.ts").write_text("export {};\n", encoding="utf-8")
            agents = source / "runtime" / "opencode" / "agents"
            agents.mkdir(parents=True)
            for name in installer.AGENT_FILES:
                (agents / name).write_text("# agent\n", encoding="utf-8")
            skill = source / "skills" / "demo"
            cache = skill / "scripts" / "__pycache__"
            cache.mkdir(parents=True)
            (skill / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
            (skill / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
            (cache / "run.cpython-311.pyc").write_bytes(b"\x00")
            (skill / "stray.pyc").write_bytes(b"\x00")
            (skill / "archive_root.conf").write_text("/tmp/kb\n", encoding="utf-8")

            home = base / "opencode"
            installer.install(source, home)
            managed = json.loads((home / installer.STATE_FILE).read_text(encoding="utf-8"))["managed_files"]
            self.assertIn("skills/demo/scripts/run.py", managed)
            self.assertEqual([key for key in managed if key.endswith(".pyc")], [])
            self.assertFalse([key for key in managed if "__pycache__" in key])
            self.assertFalse((home / "skills" / "demo" / "scripts" / "__pycache__").exists())
            self.assertFalse((home / "skills" / "demo" / "stray.pyc").exists())
            self.assertFalse((home / "skills" / "demo" / "archive_root.conf").exists())
            self.assertNotIn("skills/demo/archive_root.conf", managed)

    @unittest.skipIf(os.name == "nt", "Windows does not enforce POSIX permission bits: chmod(0o600) reports 0o666")
    def test_install_preserves_config_mode_and_hardens_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            config = home / "opencode.json"
            config.write_text(json.dumps({"provider": {"p": {"options": {"apiKey": "k"}}}}), encoding="utf-8")
            config.chmod(0o600)
            installer.install(ROOT, home)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)
            backups = list((home / "backups").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o700)
            self.assertEqual((backups[0] / "opencode.json").stat().st_mode & 0o777, 0o600)

    def test_reinstall_removes_unmodified_stale_managed_files_and_keeps_edited_ones(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            (source / "docs").mkdir(parents=True)
            (source / "schemas").mkdir(parents=True)
            (source / "shared" / "team-contracts").mkdir(parents=True)
            (source / "runtime" / "core").mkdir(parents=True)
            (source / "runtime" / "core" / "mode.ts").write_text("export {};\n", encoding="utf-8")
            plugin = source / "runtime" / "opencode" / "plugins" / "vibe-v2"
            plugin.mkdir(parents=True)
            (plugin / "index.ts").write_text("export {};\n", encoding="utf-8")
            agents = source / "runtime" / "opencode" / "agents"
            agents.mkdir(parents=True)
            for name in installer.AGENT_FILES:
                (agents / name).write_text("# agent\n", encoding="utf-8")
            for skill in ("old", "edited", "kept"):
                (source / "skills" / skill).mkdir(parents=True)
                (source / "skills" / skill / "SKILL.md").write_text(f"---\nname: {skill}\n---\n", encoding="utf-8")
            home = base / "opencode"
            installer.install(source, home)
            (home / "skills" / "edited" / "SKILL.md").write_text("user edit", encoding="utf-8")
            import shutil as _shutil
            _shutil.rmtree(source / "skills" / "old")
            _shutil.rmtree(source / "skills" / "edited")
            installer.install(source, home)
            self.assertFalse((home / "skills" / "old" / "SKILL.md").exists())
            self.assertFalse((home / "skills" / "old").exists(), "removing stale files must prune emptied skill directories")
            self.assertEqual((home / "skills" / "edited" / "SKILL.md").read_text(encoding="utf-8"), "user edit")
            self.assertTrue((home / "skills" / "kept" / "SKILL.md").is_file())
            managed = json.loads((home / installer.STATE_FILE).read_text(encoding="utf-8"))["managed_files"]
            self.assertNotIn("skills/old/SKILL.md", managed)
            self.assertNotIn("skills/edited/SKILL.md", managed)
            installer.verify(source, home)

    def test_upgrade_removes_six_retired_skills_but_preserves_user_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            old = base / "previous"
            shutil.copytree(ROOT, old, ignore=shutil.ignore_patterns("node_modules", "__pycache__", ".git"))
            for name in RETIRED_SKILLS:
                skill = old / "skills" / name
                skill.mkdir()
                (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
                (skill / "scripts").mkdir()
                (skill / "scripts" / "old_helper.py").write_text("# previous helper\n", encoding="utf-8")
            home = base / "opencode"
            home.mkdir()
            config = {"plugin": ["user-plugin"], "model": "user/example", "provider": {"user": {}}, "mcp": {"private": {"type": "remote", "url": "https://example.invalid"}}}
            (home / "opencode.json").write_text(json.dumps(config), encoding="utf-8")
            installer.install(old, home)
            archive_setting = home / "skills/a-project-archive/archive_root.conf"
            archive_setting.write_text("/user/archive\n", encoding="utf-8")
            edited = home / "skills/b-plan-stress-test/SKILL.md"
            edited.write_text("user-edited skill", encoding="utf-8")
            custom = home / "skills/custom/SKILL.md"
            custom.parent.mkdir()
            custom.write_text("user-owned skill", encoding="utf-8")
            installer.install(ROOT, home)
            installer.verify(ROOT, home)
            state = json.loads((home / installer.STATE_FILE).read_text(encoding="utf-8"))["managed_files"]
            for name in RETIRED_SKILLS:
                self.assertFalse(any(key.startswith(f"skills/{name}/") for key in state), name)
                self.assertFalse((home / "skills" / name / "scripts/old_helper.py").exists(), name)
                if name != "b-plan-stress-test":
                    self.assertFalse((home / "skills" / name / "SKILL.md").exists(), name)
            self.assertEqual(archive_setting.read_text(), "/user/archive\n")
            self.assertEqual(edited.read_text(), "user-edited skill")
            self.assertEqual(custom.read_text(), "user-owned skill")
            installed = json.loads((home / "opencode.json").read_text())
            for key in config:
                self.assertEqual(installed[key], config[key] + [installer.PLUGIN_SPEC] if key == "plugin" else config[key])
            installer.uninstall(home)
            self.assertEqual(json.loads((home / "opencode.json").read_text()), config)
            self.assertTrue(edited.exists() and archive_setting.exists() and custom.exists())


if __name__ == "__main__":
    unittest.main()
