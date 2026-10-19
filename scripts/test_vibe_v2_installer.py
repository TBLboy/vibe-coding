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
            installer.verify(ROOT, home)
            installer.uninstall(home)
            restored = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(restored, original)
            self.assertFalse((home / installer.STATE_FILE).exists())

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


if __name__ == "__main__":
    unittest.main()
