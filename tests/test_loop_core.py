from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from init_project import initialize_project
from loop_state import (
    apply_decision,
    evaluate_goal,
    invalidate_evidence,
    load_active_run,
    load_yaml,
    record_evidence,
    restore_active_run,
    save_active_run,
    save_yaml,
    sync_native_goal,
)
from validate_project import validate


class LoopCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        initialize_project(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_fresh_template_validates(self) -> None:
        self.assertEqual(validate(self.root), [])

    def test_clarification_gate_blocks_later_phase(self) -> None:
        workflow_path = self.root / ".project-log/workflow.yaml"
        workflow = load_yaml(workflow_path)
        workflow["current_phase"] = "requirement-baseline"
        save_yaml(workflow_path, workflow)
        errors = validate(self.root)
        self.assertTrue(any("clarification gate" in error for error in errors))

        clarification_path = self.root / ".project-log/business-logic/clarification.yaml"
        clarification = load_yaml(clarification_path)
        clarification["status"] = "passed"
        clarification["gate"]["status"] = "passed"
        save_yaml(clarification_path, clarification)
        self.assertEqual(validate(self.root), [])

    def define_goal(self, risk: str = "normal") -> None:
        save_yaml(
            self.root / ".project-log/goals/active-goal.yaml",
            {
                "schema_version": 1,
                "goal": {
                    "id": "GOAL-001",
                    "statement": "Deliver tested behavior",
                    "success_conditions": [
                        {
                            "id": "SC-001",
                            "statement": "Behavior is verified",
                            "status": "passed",
                            "evidence_refs": ["EVID-001"],
                        }
                    ],
                    "non_goals": [],
                    "constraints": [],
                    "required_evidence": [
                        {"kind": "test", "subject": "behavior", "evidence_refs": ["EVID-001"]}
                    ],
                    "risk_level": risk,
                    "status": "active",
                    "created_at": None,
                    "updated_at": None,
                },
            },
        )

    def test_goal_requires_valid_evidence(self) -> None:
        self.define_goal()
        result = evaluate_goal(self.root)
        self.assertFalse(result["passed"])
        record_evidence(
            self.root,
            evidence_id="EVID-001",
            kind="test",
            subject="behavior",
            status="valid",
            files=[],
            requirements=[],
            tasks=[],
            command="test",
            result_ref=None,
            replace=False,
        )
        self.assertTrue(evaluate_goal(self.root)["passed"])

    def test_high_risk_goal_requires_review(self) -> None:
        self.define_goal("high")
        record_evidence(
            self.root,
            evidence_id="EVID-001",
            kind="test",
            subject="behavior",
            status="valid",
            files=[],
            requirements=[],
            tasks=[],
            command="test",
            result_ref=None,
            replace=False,
        )
        self.assertFalse(evaluate_goal(self.root)["passed"])
        record_evidence(
            self.root,
            evidence_id="EVID-REVIEW",
            kind="review",
            subject="goal-final-review",
            status="valid",
            files=[],
            requirements=[],
            tasks=[],
            command=None,
            result_ref=None,
            replace=False,
        )
        self.assertTrue(evaluate_goal(self.root)["passed"])

    def test_evidence_becomes_stale(self) -> None:
        source = self.root / "src.txt"
        source.write_text("one", encoding="utf-8")
        record_evidence(
            self.root,
            evidence_id="EVID-001",
            kind="test",
            subject="file",
            status="valid",
            files=["src.txt"],
            requirements=[],
            tasks=["TASK-001"],
            command="test",
            result_ref=None,
            replace=False,
        )
        source.write_text("two", encoding="utf-8")
        self.assertEqual(invalidate_evidence(self.root, ["src.txt"], "changed"), ["EVID-001"])
        item = load_yaml(self.root / ".project-log/loop/evidence-index.yaml")["evidence"][0]
        self.assertEqual(item["status"], "stale")

    def retry_payload(self, delta: str) -> dict:
        return {
            "decision_id": "LD-001",
            "scope": "task",
            "trigger": "verification-completed",
            "subject": {"phase": "verification", "task_id": "TASK-001"},
            "assessment": {
                "result": "failed",
                "failure_origin": "implementation",
                "failure_signature": "same-failure",
                "new_information": True,
            },
            "decision": {"action": "retry-current-task", "reason": "fix"},
            "retry_contract": {
                "hypothesis": "change fixes it",
                "delta": delta,
                "expected_evidence": "focused test",
            },
        }

    def test_no_change_retry_is_rejected(self) -> None:
        state = load_active_run(self.root)
        state["task_id"] = "TASK-001"
        save_active_run(self.root, state)
        apply_decision(self.root, self.retry_payload("change-a"))
        with self.assertRaisesRegex(ValueError, "no-change retry"):
            apply_decision(self.root, self.retry_payload("change-a"))
        apply_decision(self.root, self.retry_payload("change-b"))

    def test_native_goal_state_does_not_delete_project_goal(self) -> None:
        self.define_goal()
        sync_native_goal(self.root, "paused", "native-1")
        self.assertEqual(load_active_run(self.root)["status"], "handed-off")
        sync_native_goal(self.root, "cleared", "native-1")
        self.assertIsNotNone(load_yaml(self.root / ".project-log/goals/active-goal.yaml")["goal"])

    def test_active_run_is_rebuilt_from_decision_event(self) -> None:
        state = load_active_run(self.root)
        state["task_id"] = "TASK-001"
        save_active_run(self.root, state)
        apply_decision(self.root, self.retry_payload("change-a"))
        expected = load_active_run(self.root)["counters"]["task_attempts"]
        (self.root / ".project-log/loop/active-run.yaml").unlink()
        restored, warnings = restore_active_run(self.root, force=True)
        self.assertEqual(restored["counters"]["task_attempts"], expected)
        self.assertTrue(any("rebuilt" in warning for warning in warnings))

    def test_invalid_event_tail_is_quarantined(self) -> None:
        events = self.root / ".project-log/loop/events.jsonl"
        events.write_text(
            '{"schema_version":1,"event_id":"LE-000001","type":"run-started"}\n{bad',
            encoding="utf-8",
        )
        (self.root / ".project-log/loop/active-run.yaml").unlink()
        _, warnings = restore_active_run(self.root, force=True)
        self.assertTrue(any("quarantined" in warning for warning in warnings))
        self.assertEqual(len(list((self.root / ".project-log/loop").glob("events.corrupt-*.json"))), 1)

    def test_business_failures_return_to_the_correct_clarification_domain(self) -> None:
        for origin in ("functional-business-logic", "technical-business-logic"):
            with self.subTest(origin=origin):
                payload = {
                    "decision_id": f"LD-{origin}",
                    "subject": {"phase": "verification", "task_id": "TASK-001"},
                    "assessment": {
                        "result": "failed",
                        "failure_origin": origin,
                        "failure_signature": origin,
                        "new_information": True,
                    },
                    "decision": {
                        "action": "return-to-phase",
                        "target_phase": "business-clarification",
                        "target_domain": origin,
                        "reason": "clarify",
                    },
                }
                result = apply_decision(self.root, payload)
                self.assertEqual(result["state"]["clarification_domain"], origin)

    def test_environment_and_harness_failures_do_not_rewrite_business_phase(self) -> None:
        for origin, action in (("environment", "repair-environment"), ("verification-harness", "repair-harness")):
            with self.subTest(origin=origin):
                state = load_active_run(self.root)
                state["phase"] = "verification"
                save_active_run(self.root, state)
                payload = {
                    "decision_id": f"LD-{origin}",
                    "subject": {"phase": "verification", "task_id": "TASK-001"},
                    "assessment": {
                        "result": "failed",
                        "failure_origin": origin,
                        "failure_signature": origin,
                        "new_information": True,
                    },
                    "decision": {"action": action, "reason": "repair"},
                }
                result = apply_decision(self.root, payload)
                self.assertEqual(result["state"]["phase"], "verification")

    def test_goal_complete_updates_project_and_run_state(self) -> None:
        self.define_goal()
        record_evidence(
            self.root,
            evidence_id="EVID-001",
            kind="test",
            subject="behavior",
            status="valid",
            files=[],
            requirements=[],
            tasks=[],
            command="test",
            result_ref=None,
            replace=False,
        )
        payload = {
            "decision_id": "LD-COMPLETE",
            "subject": {"phase": "verification", "task_id": None},
            "assessment": {"result": "passed", "new_information": True},
            "decision": {"action": "goal-complete", "reason": "all evidence is valid"},
        }
        result = apply_decision(self.root, payload)
        self.assertEqual(result["state"]["status"], "complete")
        self.assertEqual(load_yaml(self.root / ".project-log/goals/active-goal.yaml")["goal"]["status"], "complete")


class HookTests(unittest.TestCase):
    def test_session_and_compact_hooks_emit_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            payload = json.dumps({"cwd": str(project)})
            for script in ("session_start.py", "pre_compact.py"):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "runtime/hooks" / script)],
                    input=payload,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                specific = output["hookSpecificOutput"]
                self.assertEqual(specific["hookEventName"], "SessionStart" if script == "session_start.py" else "PreCompact")
                self.assertIn("additionalContext", specific)
            self.assertTrue((project / ".project-log/loop/handoff.md").is_file())


if __name__ == "__main__":
    unittest.main()
