"""V3 PR-04: the controlled verification runner and its capability preflight.

The runner exists because the previous reviewer setup proved its capability by being
granted broad shell access (`bash: allow`, or wildcards such as `*python.exe -m
pytest*`). That is not a capability check, it is a permission widening. These tests
pin the replacement: a trusted action registry, structured argv, an explicit preflight
that reports `verification_capability_missing`, and a traceable VerificationRun.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_store import StateError  # noqa: E402
import verification_runner as runner  # noqa: E402


class TrustedActionTests(unittest.TestCase):
    def test_unknown_actions_are_rejected(self) -> None:
        """Only registry actions may run; nothing is inferred from a command string."""
        with self.assertRaises(StateError) as caught:
            runner.build_argv("pytest-with-shell", ROOT)
        self.assertEqual(caught.exception.code, "verification_action_untrusted")
        self.assertIn("pytest-with-shell", str(caught.exception))

    def test_registry_covers_the_two_supported_test_runners(self) -> None:
        actions = runner.action_ids()
        self.assertIn("unittest", actions)
        self.assertIn("pytest", actions)
        self.assertEqual(actions, sorted(actions), actions)

    def test_argv_is_structured_and_never_a_shell_string(self) -> None:
        argv = runner.build_argv("unittest", ROOT)
        self.assertIsInstance(argv, list)
        self.assertTrue(all(isinstance(item, str) for item in argv), argv)
        self.assertIn("-m", argv)
        self.assertIn("unittest", argv)
        self.assertNotIn("&&", " ".join(argv))
        self.assertNotIn("|", " ".join(argv))


class PreflightTests(unittest.TestCase):
    def test_preflight_reports_a_missing_test_directory(self) -> None:
        """T: a capability gap is reported as `verification_capability_missing`.

        The reviewer must learn this before starting late-stage verification, not by
        discovering that the command is blocked halfway through.
        """
        with tempfile.TemporaryDirectory() as temporary:
            empty = Path(temporary)
            report = runner.preflight("unittest", empty)
            self.assertFalse(report["available"], report)
            self.assertEqual(report["code"], "verification_capability_missing")
            self.assertIn("tests", report["missing"])
            self.assertTrue(report["argv"], report)

    def test_preflight_passes_for_this_project(self) -> None:
        report = runner.preflight("unittest", ROOT)
        self.assertTrue(report["available"], report)
        self.assertIsNone(report["code"])
        self.assertEqual(report["missing"], [])
        self.assertTrue(all(check["ok"] for check in report["checks"]), report["checks"])

    def test_preflight_checks_the_interpreter_it_would_use(self) -> None:
        report = runner.preflight("unittest", ROOT, python=str(ROOT / "does-not-exist.exe"))
        self.assertFalse(report["available"], report)
        self.assertEqual(report["code"], "verification_capability_missing")
        self.assertIn("interpreter", report["missing"])


class VerificationRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "tests").mkdir()
        (self.root / "tests" / "test_sample.py").write_text(
            "import unittest\n\n\n"
            "class SampleTests(unittest.TestCase):\n"
            "    def test_passes(self) -> None:\n"
            "        self.assertEqual(1 + 1, 2)\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_run_records_a_traceable_verification_run(self) -> None:
        result = runner.run("unittest", self.root, timeout=120)
        for field in (
            "id", "action_id", "command_spec_version", "cwd", "argv", "environment",
            "started_at", "finished_at", "exit_code", "output_digest", "coverage_claims",
            "limitations",
        ):
            self.assertIn(field, result, field)
        self.assertEqual(result["action_id"], "unittest")
        self.assertEqual(result["exit_code"], 0, result.get("output_tail"))
        self.assertEqual(len(result["output_digest"]), 64)
        self.assertEqual(result["coverage_claims"]["paths"], ["tests"])
        self.assertTrue(result["started_at"] <= result["finished_at"])

    def test_a_failing_suite_reports_its_exit_code(self) -> None:
        (self.root / "tests" / "test_failing.py").write_text(
            "import unittest\n\n\n"
            "class FailingTests(unittest.TestCase):\n"
            "    def test_fails(self) -> None:\n"
            "        self.fail('deliberate')\n",
            encoding="utf-8",
        )
        result = runner.run("unittest", self.root, timeout=120)
        self.assertNotEqual(result["exit_code"], 0, result)
        self.assertIn("deliberate", result["output_tail"])

    def test_run_rejects_an_untrusted_action(self) -> None:
        with self.assertRaises(StateError) as caught:
            runner.run("rm-rf", self.root)
        self.assertEqual(caught.exception.code, "verification_action_untrusted")

    def test_shell_metacharacters_are_not_interpreted(self) -> None:
        """T: the runner never hands a shell a string, so `;` cannot chain a command."""
        marker = self.root / "pwned"
        with self.assertRaises(StateError):
            runner.run("unittest-file", self.root, path=f"tests/test_sample.py; touch {marker}")
        self.assertFalse(marker.exists(), "a path argument was executed by a shell")

    def test_file_action_stays_inside_the_test_directory(self) -> None:
        with self.assertRaises(StateError) as caught:
            runner.run("unittest-file", self.root, path="../outside.py")
        self.assertEqual(caught.exception.code, "invalid_input")


class RunnerEntryPointTests(unittest.TestCase):
    def test_module_entry_point_runs_a_preflight(self) -> None:
        """The reviewer's narrow allowlist targets this one entry point."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "verification_runner.py"), "preflight",
             "--action", "unittest", "--root", str(ROOT)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["available"], report)

    def test_module_entry_point_refuses_an_untrusted_action(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "verification_runner.py"), "run",
             "--action", "anything-else", "--root", str(ROOT)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("verification_action_untrusted", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
