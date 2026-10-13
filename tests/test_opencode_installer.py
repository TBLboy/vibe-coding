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
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _platform import (  # noqa: E402
    make_package_manager_shim,
    skip_unless_symlink,
    usable_posix_bash,
)


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


# Plugins a default install registers on the user's behalf; mirrors
# MANAGED_PLUGIN_SPECS in scripts/opencode_installer.py plus the catalog defaults.
MANAGED_PLUGINS = [
    "@prevalentware/opencode-goal-plugin@0.1.60",
    "opencode-agent-memory",
]


class OptionalIntegrationTests(unittest.TestCase):
    """The layered catalog: defaults, --with/--without, and selection idempotence."""

    def install(self, home: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return run_installer(
            "install", "--opencode-home", str(home), "--skip-preflight", *extra,
        )

    def config(self, home: Path) -> dict:
        return json.loads((home / "opencode.json").read_text(encoding="utf-8"))

    def state(self, home: Path) -> dict:
        return json.loads(
            (home / ".vibe-opencode-installation-state.json").read_text(encoding="utf-8")
        )

    def test_a_fresh_install_records_a_schema_3_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            state = self.state(home)
            self.assertEqual(state["schema"], 3)
            self.assertEqual(state["selected_integrations"]["plugins"], ["goal", "memory"])
            # Every default MCP is selected and none is missing.
            self.assertIn("github", state["selected_integrations"]["mcp"])

    def test_the_shipped_config_stays_minimal(self) -> None:
        """The package's own opencode.json must not hard-wire third-party entries."""
        source = json.loads(
            (ROOT / "runtime/opencode/opencode.json").read_text(encoding="utf-8")
        )
        self.assertEqual(sorted(source), ["$schema", "default_agent"])

    def test_mcp_entries_do_not_leak_catalog_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            for name, entry in self.config(home)["mcp"].items():
                self.assertNotIn("default_installed", entry, name)

    def test_without_then_bare_rerun_keeps_the_integration_disabled(self) -> None:
        """Deselecting is sticky: a later flagless update must not resurrect it."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            drop = run_installer(
                "update", "--opencode-home", str(home), "--skip-preflight",
                "--without-plugin", "memory", "--without-mcp", "github",
            )
            self.assertEqual(drop.returncode, 0, drop.stdout)
            self.assertNotIn("opencode-agent-memory", self.config(home)["plugin"])
            self.assertNotIn("github", self.config(home)["mcp"])

            rerun = run_installer("update", "--opencode-home", str(home), "--skip-preflight")
            self.assertEqual(rerun.returncode, 0, rerun.stdout)
            self.assertNotIn("opencode-agent-memory", self.config(home)["plugin"])
            self.assertNotIn("github", self.config(home)["mcp"])
            self.assertNotIn("opencode-agent-memory", self.state(home)["selected_integrations"]["plugins"])

    def test_with_restores_a_previously_deselected_integration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            run_installer("update", "--opencode-home", str(home), "--skip-preflight",
                          "--without-plugin", "memory")
            restore = run_installer("update", "--opencode-home", str(home), "--skip-preflight",
                                    "--with-plugin", "memory")
            self.assertEqual(restore.returncode, 0, restore.stdout)
            self.assertIn("opencode-agent-memory", self.config(home)["plugin"])

    def test_an_unknown_integration_name_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            result = self.install(home, "--with-mcp", "nope")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown mcp integration", result.stdout)
            self.assertFalse((home / "opencode.json").exists())

    def test_schema_2_state_migrates_without_losing_ownership(self) -> None:
        """A pre-layering state keeps exactly the set it already owned."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            state_path = home / ".vibe-opencode-installation-state.json"
            state = self.state(home)
            state["schema"] = 2
            state.pop("selected_integrations")
            state.pop("state_migrations", None)
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            update = run_installer("update", "--opencode-home", str(home), "--skip-preflight")
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("upgraded from schema 2 to 3", update.stdout)
            migrated = self.state(home)
            self.assertEqual(migrated["schema"], 3)
            self.assertIn("schema-2-to-3", migrated["state_migrations"])
            # Everything the old state owned is still registered and still owned.
            for spec in MANAGED_PLUGINS:
                self.assertIn(spec, self.config(home)["plugin"])
            self.assertIn("github", self.config(home)["mcp"])

    def test_a_newer_state_schema_is_refused_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            state_path = home / ".vibe-opencode-installation-state.json"
            state = self.state(home)
            state["schema"] = 99
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            result = run_installer("update", "--opencode-home", str(home), "--skip-preflight")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("newer than this installer understands", result.stdout)

    def test_list_integrations_reports_selection_without_installing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            result = run_installer(
                "install", "--opencode-home", str(home), "--list-integrations",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            report = json.loads(result.stdout)
            self.assertFalse(report["installed"])
            self.assertEqual(
                sorted(report["available"]["plugins"]), ["goal", "memory"]
            )
            self.assertFalse((home / "opencode.json").exists())

    def test_migrated_ownership_is_still_removable_by_uninstall(self) -> None:
        """A schema-2 install upgraded in place must not become unremovable."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            config_path = home / "opencode.json"
            original = {"plugin": ["user-plugin"], "model": "user/model"}
            config_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

            self.assertEqual(self.install(home).returncode, 0)
            state_path = home / ".vibe-opencode-installation-state.json"
            state = self.state(home)
            state["schema"] = 2
            state.pop("selected_integrations")
            state.pop("state_migrations", None)
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            upgrade = run_installer("update", "--opencode-home", str(home), "--skip-preflight")
            self.assertEqual(upgrade.returncode, 0, upgrade.stdout)

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8")), original)

    def test_deselecting_the_goal_plugin_keeps_verify_passing(self) -> None:
        """verify() must gate on the recorded selection, not on a hard-coded plugin."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            drop = run_installer("update", "--opencode-home", str(home), "--skip-preflight",
                                 "--without-plugin", "goal")
            self.assertEqual(drop.returncode, 0, drop.stdout)
            self.assertNotIn(
                "@prevalentware/opencode-goal-plugin@0.1.60", self.config(home)["plugin"]
            )
            verify = run_installer("verify", "--opencode-home", str(home))
            self.assertEqual(verify.returncode, 0, verify.stdout)

    def test_a_user_owned_catalog_named_mcp_is_never_overwritten_or_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            config_path = home / "opencode.json"
            mine = {"type": "remote", "url": "https://example.invalid/mine"}
            config_path.write_text(
                json.dumps({"mcp": {"context7": mine}}, indent=2), encoding="utf-8"
            )

            self.assertEqual(self.install(home).returncode, 0)
            self.assertEqual(self.config(home)["mcp"]["context7"], mine)

            self.assertEqual(
                run_installer("update", "--opencode-home", str(home), "--skip-preflight",
                              "--without-mcp", "context7").returncode, 0
            )
            self.assertEqual(self.config(home)["mcp"]["context7"], mine)

            self.assertEqual(
                run_installer("uninstall", "--opencode-home", str(home)).returncode, 0
            )
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8")), {"mcp": {"context7": mine}})

    def test_a_recorded_selection_naming_a_removed_catalog_entry_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            state_path = home / ".vibe-opencode-installation-state.json"
            state = self.state(home)
            state["selected_integrations"]["plugins"].append("retired-plugin")
            state["selected_integrations"]["mcp"].append("retired-mcp")
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            update = run_installer("update", "--opencode-home", str(home), "--skip-preflight")
            self.assertEqual(update.returncode, 0, update.stdout)
            selection = self.state(home)["selected_integrations"]
            self.assertNotIn("retired-plugin", selection["plugins"])
            self.assertNotIn("retired-mcp", selection["mcp"])


class OpenCodeInstallerTests(unittest.TestCase):
    def install(self, home: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return run_installer(
            "install",
            "--opencode-home",
            str(home),
            "--skip-preflight",
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
            self.assertTrue((home / "plugins/vibe-workflow/index.ts").is_file())
            self.assertTrue((home / "skills/a-loop-control/SKILL.md").is_file())
            self.assertTrue((home / "vibe-workflow/scripts/vibe.py").is_file())
            self.assertTrue((home / "vibe-python").is_file())
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["default_agent"], "vibe-main")
            # V2 discovers the directory plugin itself; registering it too would load it twice.
            self.assertNotIn("./plugins/vibe-workflow.ts", config["plugin"])
            self.assertEqual([item for item in config["plugin"] if str(item).startswith(".")], [])
            state = json.loads((home / ".vibe-opencode-installation-state.json").read_text(encoding="utf-8"))
            self.assertNotIn("plugin_install", state)
            self.assertIn("plugins/vibe-workflow/index.ts", state["managed_files"])
            self.assertIn("vibe-workflow/scripts/vibe.py", state["managed_files"])

            verify = run_installer("verify", "--opencode-home", str(home))
            self.assertEqual(verify.returncode, 0, verify.stdout)

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())
            self.assertFalse((home / "plugins/vibe-workflow/index.ts").exists())
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
            self.assertNotIn("./plugins/vibe-workflow.ts", config["plugin"])
            # The package ships a default MCP toolbelt; the user's own server is
            # preserved and the shipped ones are added alongside it.
            self.assertEqual(config["mcp"]["user"], original["mcp"]["user"])
            self.assertIn("context7", config["mcp"])
            self.assertEqual(config["default_agent"], "vibe-main")

            second = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight",
            )
            self.assertEqual(second.returncode, 0, second.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["plugin"].count("./plugins/vibe-workflow.ts"), 0)
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
            self.assertEqual(after["plugin"].count("./plugins/vibe-workflow.ts"), 0)
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
                "--skip-preflight",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("another-user-plugin", updated["plugin"])
            self.assertNotIn("./plugins/vibe-workflow.ts", updated["plugin"])
            self.assertEqual(updated["model"], "user/model")

    def test_managed_mcp_servers_follow_the_user_ownership_contract(self) -> None:
        """MCP entries use the same contract as the managed permission rules.

        The framework ships a default toolbelt, but the user stays in charge: an
        entry they already had is never overwritten, one they edited is handed back,
        and one they deleted is not resurrected on the next update.
        """
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            own = {"mine": {"type": "remote", "url": "https://example.invalid/mcp"}}
            (home / "opencode.json").write_text(
                json.dumps({"mcp": own}, indent=2), encoding="utf-8"
            )

            self.assertEqual(self.install(home).returncode, 0)
            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["mcp"]["mine"], own["mine"])
            self.assertIn("wikipedia", config["mcp"])

            # The user edits a managed server and deletes another one.
            config["mcp"]["wikipedia"] = {"type": "local", "command": ["my-wikipedia"]}
            config["mcp"].pop("playwright")
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["mcp"]["wikipedia"], {"type": "local", "command": ["my-wikipedia"]})
            self.assertNotIn("playwright", updated["mcp"])
            self.assertEqual(updated["mcp"]["mine"], own["mine"])

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            left = json.loads(config_path.read_text(encoding="utf-8"))
            # Everything the installer added is gone; the user's own server and their
            # edited entry survive.
            self.assertEqual(left.get("mcp", {}).get("mine"), own["mine"])
            self.assertEqual(
                left.get("mcp", {}).get("wikipedia"), {"type": "local", "command": ["my-wikipedia"]}
            )
            for name in ("context7", "gh_grep", "github", "sequential-thinking", "web-search"):
                self.assertNotIn(name, left.get("mcp", {}))

    def test_local_skill_modification_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            skill = home / "skills/a-loop-control/SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal change\n", encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight",
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

    def test_plugin_package_name_normalises_case_whitespace_and_versions(self) -> None:
        installer = load_installer_module()
        cases = {
            "@prevalentware/opencode-goal-plugin@0.1.51": "@prevalentware/opencode-goal-plugin",
            "@prevalentware/opencode-goal-plugin": "@prevalentware/opencode-goal-plugin",
            "@prevalentware/opencode-goal-plugin@latest": "@prevalentware/opencode-goal-plugin",
            "  @prevalentware/opencode-goal-plugin@0.1.51  ": "@prevalentware/opencode-goal-plugin",
            "@PREVALENTWARE/OpenCode-Goal-Plugin": "@prevalentware/opencode-goal-plugin",
            "opencode-notify@1.0.0": "opencode-notify",
            "  OpenCode-Notify  ": "opencode-notify",
        }
        for spec, expected in cases.items():
            self.assertEqual(installer.plugin_package_name(spec), expected, spec)
        # Not an installable spelling, but the normalisation must stay deterministic.
        self.assertEqual(installer.plugin_package_name("pkg@1@2"), "pkg@1")
        for odd in ("", "   ", ".", "./plugins/vibe-workflow.ts", "/abs/plugin.ts",
                    "file:///abs/plugin.ts", None, 42, ["a"], {"a": 1}):
            self.assertIsNone(installer.plugin_package_name(odd), odd)

    def test_install_runs_no_package_manager(self) -> None:
        """OpenCode V2 provides the plugin API, so install never runs npm/bun."""
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            bin_dir = workspace / "bin"
            marker = workspace / "package-manager-ran"
            for name in ("npm", "bun"):
                make_package_manager_shim(
                    bin_dir, name,
                    "import pathlib, sys\n"
                    f"pathlib.Path({str(marker)!r}).write_text('ran')\n"
                    "sys.exit(0)\n",
                )
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]

            install = run_installer(
                "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            self.assertEqual(install.returncode, 0, install.stdout)
            self.assertFalse(marker.exists(), "the installer must not run a package manager")
            self.assertFalse((home / "package.json").exists())
            self.assertFalse((home / "node_modules").exists())
            verify = run_installer("verify", "--opencode-home", str(home), env=environment)
            self.assertEqual(verify.returncode, 0, verify.stdout)

    def test_installation_state_keys_are_posix(self) -> None:
        """The state file is a cross-platform contract: keys never carry a host separator."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            install = self.install(home)
            self.assertEqual(install.returncode, 0, install.stdout)
            state = json.loads(
                (home / ".vibe-opencode-installation-state.json").read_text(encoding="utf-8")
            )
            self.assertIn("vibe-workflow/scripts/vibe.py", state["managed_files"])
            self.assertEqual(
                [key for key in state["managed_files"] if "\\" in key], [],
                "managed_files must record POSIX keys on every platform",
            )

    def test_legacy_backslash_state_keys_are_migrated(self) -> None:
        """A state file written with host separators migrates instead of conflicting."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            state_file = home / ".vibe-opencode-installation-state.json"
            state = json.loads(state_file.read_text(encoding="utf-8"))
            expected = sorted(state["managed_files"])
            # Reproduce the pre-fix spelling exactly: every separator is a backslash.
            state["managed_files"] = {
                key.replace("/", "\\"): digest for key, digest in state["managed_files"].items()
            }
            state_file.write_text(
                json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight",
            )
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("legacy path key(s)", update.stdout)

            migrated = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(sorted(migrated["managed_files"]), expected)
            self.assertEqual([key for key in migrated["managed_files"] if "\\" in key], [])

    def test_non_posix_state_key_is_refused_before_write(self) -> None:
        """The write guard must fail loudly rather than persist host separators again."""
        installer = load_installer_module()
        installer.assert_canonical_state({
            "managed_files": {"agents/alignment-reviewer.md": "h"},
            "preserved_local": ["skills/a-loop-control/SKILL.md"],
            "created_dirs": ["skills/a-loop-control"],
        })
        for malformed in (
            {"managed_files": {"agents\\alignment-reviewer.md": "h"}},
            {"preserved_local": ["skills\\a-loop-control\\SKILL.md"]},
            {"created_dirs": ["skills\\a-loop-control"]},
            {"managed_files": {"a//b": "h"}},
            {"managed_files": {"": "h"}},
        ):
            with self.assertRaises(RuntimeError, msg=malformed):
                installer.assert_canonical_state(malformed)

    def test_heal_state_normalizes_legacy_keys(self) -> None:
        installer = load_installer_module()
        healed = installer.heal_state({
            "managed_files": {"agents\\alignment-reviewer.md": "h", "agents/business-analyst.md": "g"},
            "preserved_local": ["skills\\a-loop-control\\SKILL.md"],
            "created_dirs": ["skills"],
        })
        self.assertEqual(
            sorted(healed["managed_files"]),
            ["agents/alignment-reviewer.md", "agents/business-analyst.md"],
        )
        self.assertEqual(healed["preserved_local"], ["skills/a-loop-control/SKILL.md"])
        self.assertEqual(healed["created_dirs"], ["skills"])
        self.assertEqual(healed["legacy_separator_keys"], 2)

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

    def test_install_registers_the_pinned_goal_controller(self) -> None:
        # The global rules declare @prevalentware/opencode-goal-plugin@0.1.60 as the
        # OpenCode session Goal controller, so a fresh install must actually register it.
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"

            install = self.install(home)

            self.assertEqual(install.returncode, 0, install.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertIn(
                "@prevalentware/opencode-goal-plugin@0.1.60", config["plugin"]
            )
            # The rule text names one version, so an unpinned spec must never appear.
            self.assertNotIn("@prevalentware/opencode-goal-plugin", config["plugin"])

            uninstall = run_installer("uninstall", "--opencode-home", str(home))

            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            # With nothing of the user's left, uninstall removes the file it created.
            config_path = home / "opencode.json"
            removed = (
                json.loads(config_path.read_text(encoding="utf-8"))
                if config_path.is_file()
                else {}
            )
            self.assertNotIn(
                "@prevalentware/opencode-goal-plugin@0.1.60", removed.get("plugin", [])
            )

    def test_goal_controller_the_user_already_had_is_kept_after_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            (home / "opencode.json").write_text(
                json.dumps(
                    {"plugin": ["@prevalentware/opencode-goal-plugin@0.1.60"]}, indent=2
                ),
                encoding="utf-8",
            )

            install = self.install(home)

            self.assertEqual(install.returncode, 0, install.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(
                config["plugin"].count("@prevalentware/opencode-goal-plugin@0.1.60"), 1
            )

            uninstall = run_installer("uninstall", "--opencode-home", str(home))

            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(
                config["plugin"], ["@prevalentware/opencode-goal-plugin@0.1.60"]
            )

    def test_conflicting_goal_controller_version_aborts_before_writing(self) -> None:
        # Two versions of the same package would make the declared controller ambiguous,
        # so this must fail closed instead of registering a second entry.
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            original = {
                "plugin": ["@prevalentware/opencode-goal-plugin@0.1.50"],
                "model": "user/model",
            }
            config_path = home / "opencode.json"
            config_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

            install = self.install(home)

            self.assertNotEqual(install.returncode, 0, install.stdout)
            self.assertIn("already registers", install.stdout)
            self.assertEqual(
                json.loads(config_path.read_text(encoding="utf-8")), original
            )
            self.assertFalse((home / "AGENTS.md").exists())
            # The pre-run snapshot is taken before the config merge, so this refusal
            # does leave a fresh backup directory behind. That is the documented
            # behaviour, and it is not a write into the config itself.
            self.assertTrue(
                list((home / "backups").glob("install-*")),
                "a refused version conflict should leave the pre-run backup",
            )

    def test_unpinned_goal_controller_is_treated_as_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            (home / "opencode.json").write_text(
                json.dumps({"plugin": ["@prevalentware/opencode-goal-plugin"]}, indent=2),
                encoding="utf-8",
            )

            install = self.install(home)

            self.assertNotEqual(install.returncode, 0, install.stdout)
            self.assertIn("already registers", install.stdout)

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
                "--skip-preflight",
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
            self.assertEqual(config["plugin"].count("./plugins/vibe-workflow.ts"), 0)

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            config = json.loads((home / "opencode.json").read_text(encoding="utf-8"))
            self.assertEqual(config["plugin"], [array_plugin])

    def test_update_removes_dependency_an_older_release_added(self) -> None:
        """An older release wrote @opencode-ai/plugin into package.json; update undoes it."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            package_json = home / "package.json"
            package_json.write_text(
                json.dumps({"dependencies": {"@opencode-ai/plugin": "1.18.4", "user-dep": "1.0.0"}}),
                encoding="utf-8",
            )
            state_path = home / ".vibe-opencode-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["package_json"] = {"existed": True, "previous_dependency": None}
            state["plugin_install"] = "installed"
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            update = run_installer("update", "--opencode-home", str(home), "--skip-preflight")
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertEqual(
                json.loads(package_json.read_text(encoding="utf-8")),
                {"dependencies": {"user-dep": "1.0.0"}},
            )
            migrated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertNotIn("package_json", migrated)
            self.assertNotIn("plugin_install", migrated)

    def test_update_migrates_the_v1_plugin_layout(self) -> None:
        """A V1-era install (single-file plugin, 0.1.51 Goal pin) migrates to the V2 layout."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            installer = load_installer_module()
            legacy = home / "plugins/vibe-workflow.ts"
            legacy.write_text("export const VibeWorkflowPlugin = async () => ({})\n", encoding="utf-8")
            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["plugin"] = [
                "user-plugin",
                "./plugins/vibe-workflow.ts",
                "@prevalentware/opencode-goal-plugin@0.1.51",
            ]
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            state_path = home / ".vibe-opencode-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["managed_files"]["plugins/vibe-workflow.ts"] = installer.sha256_file(legacy)
            state["opencode_config"]["plugin"] = {"present": False}
            state["opencode_config"]["plugins_added"] = {
                installer.plugin_key("@prevalentware/opencode-goal-plugin@0.1.51"): False,
            }
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            verify_before = run_installer("verify", "--opencode-home", str(home))
            self.assertNotEqual(verify_before.returncode, 0, verify_before.stdout)

            update = run_installer("update", "--opencode-home", str(home), "--skip-preflight")
            self.assertEqual(update.returncode, 0, update.stdout)
            self.assertIn("V1 single-file plugin", update.stdout)
            self.assertIn("updated the installer-owned plugin", update.stdout)
            self.assertFalse(legacy.exists())
            self.assertTrue((home / "plugins/vibe-workflow/index.ts").is_file())
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(
                config["plugin"], ["user-plugin", *MANAGED_PLUGINS]
            )
            verify = run_installer("verify", "--opencode-home", str(home))
            self.assertEqual(verify.returncode, 0, verify.stdout)

            # The migrated controller is still installer-owned, so uninstall removes it.
            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["plugin"], ["user-plugin"])

    def test_v2_plugins_key_is_used_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            config_path = home / "opencode.json"
            config_path.write_text(json.dumps({"plugins": ["user-plugin"]}), encoding="utf-8")

            install = self.install(home)
            self.assertEqual(install.returncode, 0, install.stdout)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("plugin", config)
            self.assertEqual(
                config["plugins"], ["user-plugin", *MANAGED_PLUGINS]
            )
            verify = run_installer("verify", "--opencode-home", str(home))
            self.assertEqual(verify.returncode, 0, verify.stdout)

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            self.assertEqual(json.loads(config_path.read_text(encoding="utf-8")), {"plugins": ["user-plugin"]})

    def test_both_plugin_list_keys_are_migrated_together(self) -> None:
        """A config carrying both `plugins` and `plugin` is cleaned in both lists."""
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            installer = load_installer_module()
            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config.pop("plugin", None)
            config["plugins"] = ["user-a", "@prevalentware/opencode-goal-plugin@0.1.51"]
            config["plugin"] = ["./plugins/vibe-workflow.ts", "user-b"]
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            state_path = home / ".vibe-opencode-installation-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["opencode_config"]["plugins_added"] = {
                installer.plugin_key("@prevalentware/opencode-goal-plugin@0.1.51"): False,
            }
            state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

            update = run_installer("update", "--opencode-home", str(home), "--skip-preflight")
            self.assertEqual(update.returncode, 0, update.stdout)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["plugins"], ["user-a", *MANAGED_PLUGINS])
            self.assertEqual(config["plugin"], ["user-b"])

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertEqual(uninstall.returncode, 0, uninstall.stdout)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["plugins"], ["user-a"])
            self.assertEqual(config["plugin"], ["user-b"])

    def test_goal_version_conflict_in_the_secondary_list_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            home.mkdir()
            original = {"plugins": ["user-a"], "plugin": ["@prevalentware/opencode-goal-plugin@0.1.50"]}
            (home / "opencode.json").write_text(json.dumps(original), encoding="utf-8")
            install = self.install(home)
            self.assertNotEqual(install.returncode, 0, install.stdout)
            self.assertIn("already registers", install.stdout)
            self.assertEqual(json.loads((home / "opencode.json").read_text(encoding="utf-8")), original)

    def test_preflight_refuses_an_opencode_v1_cli(self) -> None:
        for version, accepted in (("1.18.31", False), ("opencode v2.0.27", True)):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as temporary:
                workspace = Path(temporary)
                bin_dir = workspace / "bin"
                make_package_manager_shim(
                    bin_dir, "opencode", f"import sys\nprint({version!r})\nsys.exit(0)\n",
                )
                environment = os.environ.copy()
                environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]
                result = run_installer(
                    "preflight", "--opencode-home", str(workspace / "opencode"), env=environment,
                )
                if accepted:
                    self.assertEqual(result.returncode, 0, result.stdout)
                    report = json.loads(result.stdout)
                    self.assertEqual(report["opencode_version"], "2.0.27")
                    self.assertNotIn("package_manager", report)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn("V1 release", result.stdout)

    def test_preflight_warns_about_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(Path(temporary) / "foreign-site-packages")
            result = run_installer(
                "preflight", "--opencode-home", str(Path(temporary) / "opencode"), env=environment,
            )
            if result.returncode != 0 and "V1 release" in result.stdout:
                self.skipTest("the host opencode CLI is a V1 release")
            self.assertEqual(result.returncode, 0, result.stdout)
            report = json.loads(result.stdout)
            self.assertTrue(any("PYTHONPATH" in item for item in report["warnings"]), report)

    def test_install_sh_defaults_to_install_with_options_only(self) -> None:
        bash = usable_posix_bash()
        if bash is None:
            self.skipTest(
                "no POSIX bash that can consume native paths "
                "(missing, unusable, or the WSL stub on PATH)"
            )
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            # Hermetic: the wrapper resolves its interpreter from VIBE_PYTHON, the ambient
            # config home's vibe-python pointer, or PATH. Relying on the ambient HOME would
            # make this test pass or fail depending on the developer's machine and on
            # whatever environment a sandbox happens to pass through.
            environment = dict(os.environ, VIBE_PYTHON=sys.executable)
            result = subprocess.run(
                [bash, str(INSTALL_SH), "--opencode-home", str(home),
                "--skip-preflight"],
                text=True, encoding="utf-8", stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False, env=environment,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((home / "opencode.json").is_file())
            self.assertTrue((home / "AGENTS.md").is_file())

    def test_user_permission_edit_is_not_reset_by_update(self) -> None:
        # The installer template no longer ships a top-level `permission` block
        # (role boundaries live in the agent files), so this exercises the same
        # ownership mechanism through a key the user does edit by hand.
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["permission"] = {"skill": {"*": "ask"}}
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            update = run_installer(
                "update", "--opencode-home", str(home),
                "--skip-preflight",
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
            self.assertTrue((home / "plugins/vibe-workflow/index.ts").is_file())
            self.assertTrue((home / ".vibe-opencode-installation-state.json").is_file())

    def _install_failing_after_writes(self, home: Path) -> None:
        """Run install in-process and fail in the final verification, after every write."""
        installer = load_installer_module()

        def broken_verify(root: Path, target: Path) -> None:
            raise RuntimeError("injected verification failure")

        installer.verify = broken_verify
        with self.assertRaises(RuntimeError):
            installer.install_or_update(
                installer.package_root(), home, skip_preflight=True,
            )

    def test_failure_rolls_back_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self._install_failing_after_writes(home)
            self.assertFalse((home / "plugins/vibe-workflow/index.ts").exists())
            self.assertFalse((home / "vibe-workflow/scripts/vibe.py").exists())
            self.assertFalse((home / "AGENTS.md").exists())
            self.assertFalse((home / "opencode.json").exists())
            self.assertFalse((home / "package.json").exists())
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())

    def test_corrupt_package_json_blocks_uninstall_before_deleting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            (home / "package.json").write_text("{ not json", encoding="utf-8")

            uninstall = run_installer("uninstall", "--opencode-home", str(home))
            self.assertNotEqual(uninstall.returncode, 0)
            self.assertTrue((home / "plugins/vibe-workflow/index.ts").is_file())
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
                "--skip-preflight",
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
        # The shipped template no longer declares a top-level `permission` block,
        # so the managed rule is created through merge_config directly; the
        # behavior under test is ownership hand-back, not the template contents.
        module = load_installer_module()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "package"
            surface = root / "runtime/opencode"
            surface.mkdir(parents=True)
            (surface / "opencode.json").write_text(
                json.dumps({"default_agent": "vibe-main", "permission": {"skill": {"*": "allow"}}}),
                encoding="utf-8",
            )
            home = Path(temporary) / "home"
            home.mkdir()

            ownership = module.merge_config(home, root, {})
            self.assertEqual(ownership["permissions_added"]["skill"]["*"]["installed"], "allow")

            config_path = home / "opencode.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            del config["permission"]["skill"]["*"]
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

            second = module.merge_config(home, root, ownership)
            updated = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertNotIn("*", (updated.get("permission") or {}).get("skill") or {})
            # The user-facing notice is part of the contract: a silently dropped
            # managed rule looks identical to a successful update.
            self.assertIn(
                "managed rule removed by the user",
                " ".join(str(note) for note in second.get("notes") or []),
            )

    def test_failure_leaves_no_created_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self._install_failing_after_writes(home)
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
            self.assertTrue((home / "plugins/vibe-workflow/index.ts").is_file())

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
            self.assertTrue((home / "plugins/vibe-workflow/index.ts").is_file())

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
            self.assertTrue((home / "plugins/vibe-workflow/index.ts").is_file())

    def test_existing_lockfile_is_restored_after_failed_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "opencode"
            self.assertEqual(self.install(home).returncode, 0)
            lockfile = home / "package-lock.json"
            lockfile.write_text('{"original": true}', encoding="utf-8")
            installed = (home / "plugins/vibe-workflow/index.ts").read_bytes()

            self._install_failing_after_writes(home)
            self.assertEqual(lockfile.read_text(encoding="utf-8"), '{"original": true}')
            self.assertEqual((home / "plugins/vibe-workflow/index.ts").read_bytes(), installed)
            self.assertTrue((home / ".vibe-opencode-installation-state.json").is_file())

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
                "--skip-preflight",
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

    @skip_unless_symlink
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
            self.assertFalse((outside / "vibe-workflow").exists())
            self.assertEqual(list(outside.iterdir()), [])

    @skip_unless_symlink
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

    @skip_unless_symlink
    def test_symlinked_node_modules_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "opencode"
            outside = workspace / "outside"
            outside.mkdir()
            home.mkdir()
            os.symlink(outside, home / "node_modules")

            install = self.install(home)
            self.assertNotEqual(install.returncode, 0)
            self.assertIn("outside the OpenCode home", install.stdout)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())

    @skip_unless_symlink
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
            make_package_manager_shim(
                bin_dir, "npm",
                "import pathlib\n"
                "cwd = pathlib.Path.cwd()\n"
                "t = cwd / 'node_modules/@opencode-ai/plugin'\n"
                "t.mkdir(parents=True, exist_ok=True)\n"
                "(t / 'package.json').write_text('{\"version\": \"1.18.4\"}')\n",
            )
            environment = os.environ.copy()
            environment["PATH"] = str(bin_dir) + os.pathsep + environment["PATH"]

            install = run_installer(
                "install", "--opencode-home", str(home), "--skip-preflight", env=environment,
            )
            self.assertNotEqual(install.returncode, 0)
            self.assertIn("outside the OpenCode home", install.stdout)
            self.assertEqual(list(outside.iterdir()), [])
            self.assertFalse((home / ".vibe-opencode-installation-state.json").exists())

    @skip_unless_symlink
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
