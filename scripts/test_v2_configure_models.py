"""Behavioral tests for the b-opencode-model-config helper (no external packages)."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/b-opencode-model-config/scripts/configure_models.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


class ConfigureModelsTests(unittest.TestCase):
    def write_config(self, directory: Path) -> Path:
        config = directory / "opencode.json"
        config.write_text(json.dumps({
            "model": "demo/alpha",
            "provider": {"demo": {"options": {"apiKey": "secret-not-printed"}, "models": {
                "alpha": {"name": "Alpha", "attachment": True, "limit": {"context": 200000, "output": 8192}},
                "beta": {"name": "Beta"},
            }}},
            "mcp": {"keep": {"type": "remote", "url": "https://example.invalid"}},
        }, indent=2), encoding="utf-8")
        config.chmod(0o600)
        return config

    def test_applies_defaults_removes_legacy_flag_and_preserves_unrelated_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = self.write_config(Path(temporary))
            result = run("--provider", "demo", "--config", str(config))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("secret-not-printed", result.stdout + result.stderr)
            data = json.loads(config.read_text(encoding="utf-8"))
            alpha = data["provider"]["demo"]["models"]["alpha"]
            self.assertNotIn("attachment", alpha)
            self.assertEqual(alpha["limit"], {"context": 500000, "output": 32000})  # --output default
            self.assertEqual(alpha["modalities"]["input"], ["text", "image"])
            self.assertEqual(data["provider"]["demo"]["models"]["beta"]["limit"]["context"], 500000)
            self.assertEqual(data["model"], "demo/alpha")
            self.assertEqual(data["mcp"], {"keep": {"type": "remote", "url": "https://example.invalid"}})
            self.assertEqual(data["provider"]["demo"]["options"]["apiKey"], "secret-not-printed")
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_dry_run_writes_nothing_and_second_run_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = self.write_config(Path(temporary))
            before = config.read_text(encoding="utf-8")
            dry = run("--provider", "demo", "--config", str(config), "--dry-run")
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertEqual(config.read_text(encoding="utf-8"), before)
            self.assertEqual(run("--provider", "demo", "--config", str(config)).returncode, 0)
            after = config.read_text(encoding="utf-8")
            second = run("--provider", "demo", "--config", str(config))
            self.assertEqual(second.returncode, 0)
            self.assertIn("nothing to write", second.stdout)
            self.assertEqual(config.read_text(encoding="utf-8"), after)

    def test_unknown_provider_or_model_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = self.write_config(Path(temporary))
            self.assertEqual(run("--provider", "nope", "--config", str(config)).returncode, 2)
            self.assertEqual(run("--provider", "demo", "--model", "gamma", "--config", str(config)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
