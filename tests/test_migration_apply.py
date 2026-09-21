"""TASK-040: explicit, resumable and rollback-safe legacy migration."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
VIBE = SCRIPTS / "vibe.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_context import open_store  # noqa: E402


def run_vibe(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VIBE), "--root", str(root), *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )


def write_yaml(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False, allow_unicode=True), encoding="utf-8")


def make_legacy(root: Path) -> None:
    write_yaml(root / ".project-log/goals/active-goal.yaml", {
        "schema_version": 1,
        "goal": {
            "id": "GOAL-LEGACY", "statement": "Legacy goal", "status": "active",
            "success_conditions": [], "required_evidence": [],
        },
    })
    write_yaml(root / ".project-log/tasks/task-list.yaml", {
        "version": 1, "active_goal": "GOAL-LEGACY",
        "tasks": [
            {
                "id": "TASK-PENDING", "title": "Pending task", "status": "pending",
                "phase": "implementation", "depends_on": [], "related_decisions": [],
                "blocked_by_questions": [],
            },
            {
                "id": "TASK-DONE", "title": "Done task", "status": "done",
                "phase": "implementation", "depends_on": [], "related_decisions": [],
                "blocked_by_questions": [],
            },
        ],
    })
    write_yaml(root / ".project-log/decisions/decision-log.yaml", {
        "version": 1,
        "decisions": [{
            "id": "DEC-LEGACY", "title": "Legacy decision", "statement": "Keep history",
            "status": "active", "authority": "B",
        }],
    })
    write_yaml(root / ".project-log/business-logic/open-questions.yaml", {
        "version": 1,
        "questions": [{
            "id": "Q-LEGACY", "question": "Legacy question", "status": "open",
            "authority": "B",
        }],
    })
    write_yaml(root / ".project-log/loop/evidence-index.yaml", {
        "schema_version": 1,
        "evidence": [{
            "id": "EVID-LEGACY", "kind": "test", "subject": "done task",
            "status": "valid", "covers": {"files": [], "requirements": [], "tasks": ["TASK-DONE"]},
            "version_binding": {"file_hashes": {}},
        }],
    })
    write_yaml(root / ".project-log/loop/active-run.yaml", {
        "schema_version": 1, "run_id": "RUN-LEGACY", "task_id": "TASK-PENDING",
        "status": "active", "phase": "implementation",
    })


class MigrationApplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        make_legacy(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def preview(self) -> dict:
        result = run_vibe(self.root, "migrate", "preview")
        self.assertEqual(result.returncode, 0, result.stdout)
        return json.loads(result.stdout)

    def test_apply_requires_matching_confirmation_and_preserves_source(self) -> None:
        before = (self.root / ".project-log/tasks/task-list.yaml").read_bytes()
        report = self.preview()
        result = run_vibe(self.root, "migrate", "apply", "--confirm", "wrong")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("confirmation_required", result.stdout)
        self.assertEqual((self.root / ".project-log/tasks/task-list.yaml").read_bytes(), before)
        self.assertFalse((self.root / ".project-log/state-format.json").exists())

    def test_apply_switches_to_format_two_and_keeps_unmapped_history(self) -> None:
        report = self.preview()
        result = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.root / ".project-log/state-format.json").is_file())
        store = open_store(self.root)
        self.assertEqual(store.get_goal("GOAL-LEGACY")["title"], "Legacy goal")
        self.assertEqual(store.get_task("TASK-PENDING")["status"], "ready")
        self.assertEqual(store.get_task("TASK-DONE")["status"], "implemented-unverified")
        self.assertEqual(store.get_evidence("EVID-LEGACY")["status"], "valid")
        self.assertEqual(store.get_record("decision", "DEC-LEGACY")["status"], "active")
        self.assertEqual(store.get_record("alignment", "Q-LEGACY")["status"], "open")
        self.assertTrue((self.root / ".project-log/legacy/tasks/task-list.yaml").is_file())

    def test_rollback_restores_legacy_files_and_preserves_new_writes(self) -> None:
        report = self.preview()
        result = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertEqual(result.returncode, 0, result.stdout)
        store = open_store(self.root)
        store.apply({
            "schema_version": 1, "command_id": "d" * 32,
            "expected_revision": store.status()["revision"],
            "action": "evidence.record",
            "payload": {
                "id": "EVID-AFTER", "kind": "test", "subject": "after migration",
                "status": "valid",
            },
        })

        result = run_vibe(self.root, "migrate", "rollback")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.root / ".project-log/state-format.json").exists())
        self.assertTrue((self.root / ".project-log/tasks/task-list.yaml").is_file())
        self.assertTrue((self.root / ".project-log/legacy/new-writes/bundle.json").is_file())
        self.assertIn("EVID-AFTER", (
            self.root / ".project-log/legacy/new-writes/bundle.json"
        ).read_text(encoding="utf-8"))

    def test_duplicate_ids_are_blocking_conflicts(self) -> None:
        document = yaml.safe_load((self.root / ".project-log/tasks/task-list.yaml").read_text(encoding="utf-8"))
        document["tasks"].append(dict(document["tasks"][0]))
        write_yaml(self.root / ".project-log/tasks/task-list.yaml", document)

        report = self.preview()

        self.assertFalse(report["ready"])
        self.assertTrue(any(item["kind"] == "duplicate_id" for item in report["conflicts"]))
        result = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / ".project-log/state-format.json").exists())

    def test_resume_validates_an_already_switched_migration(self) -> None:
        report = self.preview()
        applied = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertEqual(applied.returncode, 0, applied.stdout)

        result = run_vibe(self.root, "migrate", "resume")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "switched")

    def test_unknown_legacy_fields_are_preserved_in_unmapped(self) -> None:
        document = yaml.safe_load((self.root / ".project-log/tasks/task-list.yaml").read_text(encoding="utf-8"))
        document["tasks"][0]["future_only_field"] = {"kept": True}
        write_yaml(self.root / ".project-log/tasks/task-list.yaml", document)

        report = self.preview()
        self.assertTrue(report["ready"])
        result = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])

        self.assertEqual(result.returncode, 0, result.stdout)
        unmapped = json.loads((
            self.root / ".project-log/legacy/unmapped/unmapped.json"
        ).read_text(encoding="utf-8"))
        self.assertTrue(any(
            entry.get("kind") == "unknown_task_field" for entry in unmapped["entries"]
        ))

    def test_source_change_after_preview_blocks_apply(self) -> None:
        report = self.preview()
        (self.root / ".project-log/tasks/task-list.yaml").write_text(
            "tasks: []\n", encoding="utf-8"
        )
        result = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("confirmation_required", result.stdout)
        self.assertIn("source may have changed", result.stdout)
        self.assertFalse((self.root / ".project-log/state-format.json").exists())

    def test_apply_creates_the_format_two_layout(self) -> None:
        report = self.preview()
        result = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertEqual(result.returncode, 0, result.stdout)
        log = self.root / ".project-log"
        self.assertTrue((log / ".state").is_dir())
        self.assertEqual(
            (log / ".gitignore").read_text(encoding="utf-8"),
            ".state/\n.migration/\nlegacy/new-writes/\n",
        )
        self.assertEqual(
            (log / "exchange/.gitattributes").read_text(encoding="utf-8"), "* -text\n"
        )

    def test_long_form_docs_are_not_relocated_by_migration(self) -> None:
        document = self.root / ".project-log/docs/note.md"
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text("# Legacy note\n", encoding="utf-8")

        report = self.preview()
        result = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(document.read_text(encoding="utf-8"), "# Legacy note\n")
        self.assertFalse((self.root / ".project-log/legacy/docs/note.md").exists())

    def test_resume_finishes_an_interrupted_switch(self) -> None:
        report = self.preview()
        applied = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertEqual(applied.returncode, 0, applied.stdout)
        journal = json.loads(
            (self.root / ".project-log/.migration/journal.json").read_text(encoding="utf-8")
        )
        staging = Path(journal["staging"])
        staging.mkdir(parents=True, exist_ok=True)

        # Rewind to the state an interrupted switch leaves behind: the database is
        # still staged and the marker is missing, while legacy files already moved.
        store = open_store(self.root)
        database = store.path
        store = None
        (self.root / ".project-log/state-format.json").unlink()
        database.replace(staging / "state.sqlite3")

        resumed = run_vibe(self.root, "migrate", "resume")

        self.assertEqual(resumed.returncode, 0, resumed.stdout)
        self.assertEqual(json.loads(resumed.stdout)["status"], "switched")
        self.assertTrue((self.root / ".project-log/state-format.json").is_file())
        self.assertTrue((self.root / ".project-log/legacy/tasks/task-list.yaml").is_file())
        self.assertEqual(open_store(self.root).get_goal("GOAL-LEGACY")["title"], "Legacy goal")

    def test_resume_recovers_a_marker_without_a_store(self) -> None:
        report = self.preview()
        applied = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertEqual(applied.returncode, 0, applied.stdout)
        journal = json.loads(
            (self.root / ".project-log/.migration/journal.json").read_text(encoding="utf-8")
        )
        staging = Path(journal["staging"])
        staging.mkdir(parents=True, exist_ok=True)
        open_store(self.root).path.replace(staging / "state.sqlite3")

        resumed = run_vibe(self.root, "migrate", "resume")

        self.assertEqual(resumed.returncode, 0, resumed.stdout)
        self.assertEqual(json.loads(resumed.stdout)["status"], "switched")
        self.assertEqual(open_store(self.root).get_task("TASK-DONE")["status"], "implemented-unverified")

    def test_rollback_removes_only_the_layout_migration_created(self) -> None:
        report = self.preview()
        applied = run_vibe(self.root, "migrate", "apply", "--confirm", report["preview_hash"])
        self.assertEqual(applied.returncode, 0, applied.stdout)

        result = run_vibe(self.root, "migrate", "rollback")

        self.assertEqual(result.returncode, 0, result.stdout)
        log = self.root / ".project-log"
        self.assertFalse((log / ".gitignore").exists())
        self.assertFalse((log / "exchange").exists())
        self.assertTrue((log / "tasks/task-list.yaml").is_file())

    def test_resume_finishes_a_switch_interrupted_after_each_replace(self) -> None:
        import state_migrate

        for index in (1, 2, 3):
            with self.subTest(fail_after_replace=index), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                make_legacy(project)
                report = state_migrate.preview(project)
                original = state_migrate.os.replace
                calls = {"count": 0}

                def faulting_replace(source, destination, _index=index):
                    calls["count"] += 1
                    outcome = original(source, destination)
                    if calls["count"] == _index:
                        raise OSError(f"injected failure after os.replace #{_index}")
                    return outcome

                state_migrate.os.replace = faulting_replace
                try:
                    with self.assertRaises(OSError):
                        state_migrate.apply(project, report["preview_hash"])
                finally:
                    state_migrate.os.replace = original

                resumed = state_migrate.resume(project)

                self.assertEqual(resumed["status"], "switched")
                self.assertTrue((project / ".project-log/state-format.json").is_file())
                store = open_store(project)
                self.assertEqual(store.validate(), [])
                self.assertEqual(store.get_task("TASK-PENDING")["status"], "ready")
                self.assertEqual(store.get_goal("GOAL-LEGACY")["title"], "Legacy goal")


if __name__ == "__main__":
    unittest.main()
