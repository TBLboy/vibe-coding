"""Isolated acceptance tests for the V2 installer without external packages."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("v2installer", ROOT / "scripts" / "vibe_v2_installer.py")
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


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
            self.assertTrue((home / "skills" / "b-opencode-model-config" / "SKILL.md").is_file())
            installer.verify(ROOT, home)
            installer.uninstall(home)
            restored = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(restored, original)
            self.assertFalse((home / installer.STATE_FILE).exists())
            self.assertFalse((home / "skills" / "a-verification" / "SKILL.md").exists())

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

    def test_install_skips_python_bytecode_caches(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
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

            home = base / "opencode"
            installer.install(source, home)
            managed = json.loads((home / installer.STATE_FILE).read_text(encoding="utf-8"))["managed_files"]
            self.assertIn("skills/demo/scripts/run.py", managed)
            self.assertEqual([key for key in managed if key.endswith(".pyc")], [])
            self.assertFalse([key for key in managed if "__pycache__" in key])
            self.assertFalse((home / "skills" / "demo" / "scripts" / "__pycache__").exists())
            self.assertFalse((home / "skills" / "demo" / "stray.pyc").exists())

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
            self.assertEqual((home / "skills" / "edited" / "SKILL.md").read_text(encoding="utf-8"), "user edit")
            self.assertTrue((home / "skills" / "kept" / "SKILL.md").is_file())
            managed = json.loads((home / installer.STATE_FILE).read_text(encoding="utf-8"))["managed_files"]
            self.assertNotIn("skills/old/SKILL.md", managed)
            self.assertNotIn("skills/edited/SKILL.md", managed)
            installer.verify(source, home)


if __name__ == "__main__":
    unittest.main()
