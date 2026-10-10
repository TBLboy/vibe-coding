"""V3 PR-04: the controlled verification runner and its capability preflight.

The runner exists because the previous reviewer setup proved its capability by being
granted broad shell access (`bash: allow`, or wildcards such as `*python.exe -m
pytest*`). That is not a capability check, it is a permission widening. These tests
pin the replacement: a trusted action registry, structured argv, an explicit preflight
that reports `verification_capability_missing`, and a traceable VerificationRun.
"""
from __future__ import annotations

import hashlib
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

    def test_preflight_reports_an_unsupported_interpreter_version(self) -> None:
        """T: a review must not silently run under an older interpreter.

        The allowlist can no longer be pinned to a POSIX-only wrapper, so the version
        gate lives in the runner: whatever interpreter a reviewer reaches for, an
        unsupported one is reported as a capability gap instead of quietly downgrading
        the verification.
        """
        original = runner.MINIMUM_PYTHON
        try:
            runner.MINIMUM_PYTHON = (99, 0)
            report = runner.preflight("unittest", ROOT)
        finally:
            runner.MINIMUM_PYTHON = original
        self.assertFalse(report["available"], report)
        self.assertEqual(report["code"], "verification_capability_missing")
        self.assertIn("python>=99.0", report["missing"])
        self.assertTrue(
            any(not check["ok"] for check in report["checks"]), report["checks"])
        # And the unmodified runner accepts the interpreter actually running this suite.
        self.assertTrue(runner.preflight("unittest", ROOT)["available"])


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


class HashActionTests(unittest.TestCase):
    """Digest re-derivation must go through the same trusted registry as every check.

    Before this action existed the reviewer allowlist carried `sha256sum *`, which does
    not exist on Windows: the only way left to check a recorded digest was to leave the
    controlled entry point. `hash` restores that capability on every platform without
    handing out a general-purpose shell.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "artifact.txt").write_bytes(b"verified bytes\n")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_hash_is_a_registered_action(self) -> None:
        self.assertIn("hash", runner.action_ids())

    def test_hash_argv_is_a_fixed_script_plus_paths(self) -> None:
        argv = runner.build_argv("hash", self.root, paths=["artifact.txt"])
        self.assertEqual(argv[0], runner.interpreter())
        self.assertEqual(argv[1], "-c")
        self.assertEqual(argv[3:], ["artifact.txt"])
        self.assertNotIn("&&", " ".join(argv))
        self.assertNotIn("|", " ".join(argv))

    def test_hash_reproduces_an_independently_computed_digest(self) -> None:
        expected = hashlib.sha256((self.root / "artifact.txt").read_bytes()).hexdigest()
        result = runner.run("hash", self.root, paths=["artifact.txt"], timeout=60)
        self.assertEqual(result["exit_code"], 0, result.get("output_tail"))
        self.assertIn(expected, result["output_tail"])
        self.assertEqual(result["coverage_claims"]["paths"], ["artifact.txt"])

    def test_hash_rejects_anything_that_leaves_the_project(self) -> None:
        for bad in ("../outside.txt", "C:/Windows/win.ini", "artifact.txt; echo pwned"):
            with self.assertRaises(StateError) as caught:
                runner.build_argv("hash", self.root, paths=[bad])
            self.assertEqual(caught.exception.code, "invalid_input", bad)

    def test_hash_requires_at_least_one_named_file(self) -> None:
        with self.assertRaises(StateError) as caught:
            runner.build_argv("hash", self.root)
        self.assertEqual(caught.exception.code, "invalid_input")

    def test_hash_refuses_a_directory(self) -> None:
        with self.assertRaises(StateError) as caught:
            runner.build_argv("hash", self.root, paths=["."])
        self.assertEqual(caught.exception.code, "invalid_input")

    def test_reviewer_allowlists_carry_no_posix_only_hashing_tool(self) -> None:
        """A permission entry for a command that cannot exist is a broken capability.

        The allowlist is a contract about what a reviewer can do here, so it must not
        advertise a tool that is missing on this platform; the registry action is the
        supported way to re-derive a digest.
        """
        for name in ("verification-reviewer.md", "alignment-reviewer.md"):
            text = (ROOT / "runtime" / "opencode" / "agents" / name).read_text(encoding="utf-8")
            self.assertNotIn("sha256sum", text, name)
            self.assertIn("*verification_runner.py run*", text, name)


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


class TargetedRunTests(unittest.TestCase):
    """TASK-121: a targeted run must execute something, or it is not evidence.

    `unittest discover -p` compares its pattern against the *basename*, so the resolved
    relative path used to match nothing: the action exited 0 after `Ran 0 tests`, which
    reads exactly like a green targeted run.
    """

    def test_unittest_file_actually_runs_the_named_file(self) -> None:
        # Deliberately *not* this file: `unittest-file` on test_verification_runner.py
        # would re-run this very test and recurse.
        report = runner.run("unittest-file", ROOT, path="tests/test_docs_consistency.py")
        self.assertEqual(report["exit_code"], 0, report["output_tail"])
        self.assertIn("Ran ", report["output_tail"])
        self.assertNotIn("Ran 0 tests", report["output_tail"])

    def test_a_file_with_no_tests_is_refused_instead_of_passing(self) -> None:
        """A run that executes nothing is refused, not recorded as a pass."""
        with self.assertRaises(StateError) as caught:
            runner.run("unittest-file", ROOT, path="tests/_platform.py")
        self.assertEqual(caught.exception.code, "verification_no_tests")


if __name__ == "__main__":
    unittest.main()
