"""Bootstrap of the Vibe runtime interpreter.

This file used to also cover the codex installer (`scripts/global_installer.py`).
That installer, its delivery face and its tests were removed; the interpreter
bootstrap is shared -- `runtime/opencode/install.sh` tells the user to run it -- so
its coverage stays, moved to a file named for what it actually tests.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts/bootstrap_vibe_python.py"


def write_test_executable(directory: Path, name: str, python_source: str) -> Path:
    if os.name != "nt":
        path = directory / name
        path.write_text("#!/usr/bin/env python3\n" + python_source, encoding="utf-8")
        path.chmod(0o700)
        return path

    script = directory / f"{name}.py"
    script.write_text(python_source, encoding="utf-8")
    path = directory / f"{name}.cmd"
    path.write_text(
        "@echo off\n"
        f'"{sys.executable}" "%~dp0{name}.py" %*\n',
        encoding="utf-8",
    )
    return path


def write_fake_interpreter(
    directory: Path,
    name: str,
    marker: Path,
    *,
    pip_succeeds: bool = True,
) -> Path:
    """A stand-in interpreter that is Python 3.11+ but starts without the Vibe requirements."""
    source = (
        "import os, pathlib, sys\n"
        "args = sys.argv[1:]\n"
        "identity = os.environ.get('FAKE_PYTHON_IDENTITY', 'fake-python')\n"
        f"marker = pathlib.Path({str(marker)!r})\n"
        "if '-m' in args and 'pip' in args:\n"
        f"    {'marker.touch()' if pip_succeeds else 'pass'}\n"
        f"    raise SystemExit({0 if pip_succeeds else 1})\n"
        "if args and args[0] == '-c':\n"
        "    if 'yaml' in args[1]:\n"
        "        if marker.exists():\n"
        "            print(identity)\n"
        "            raise SystemExit(0)\n"
        "        print('ModuleNotFoundError: No module named yaml', file=sys.stderr)\n"
        "        raise SystemExit(1)\n"
        "    print(identity)\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(1)\n"
    )
    return write_test_executable(directory, name, source)


def write_fake_conda(directory: Path, name: str, created: Path) -> Path:
    return write_test_executable(
        directory,
        name,
        "import pathlib, sys\n"
        f"created = pathlib.Path({str(created)!r})\n"
        "if len(sys.argv) > 1 and sys.argv[1] == 'create':\n"
        "    created.touch()\n"
        "    raise SystemExit(0)\n"
        "if len(sys.argv) > 1 and sys.argv[1] == 'run' and created.exists():\n"
        f"    print({str(Path(sys.executable).resolve())!r})\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(1)\n",
    )


def load_bootstrap():
    """Import the bootstrap script so its resolution helpers can be tested directly."""
    spec = importlib.util.spec_from_file_location("bootstrap_vibe_python_under_test", BOOTSTRAP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BootstrapTests(unittest.TestCase):
    def test_bootstrap_creates_missing_conda_environment(self) -> None:
        if sys.version_info < (3, 11):
            self.skipTest("bootstrap integration requires Python 3.11+")
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            created = workspace / "created"
            manager = write_test_executable(
                workspace,
                "conda",
                "import pathlib, sys\n"
                f"created = pathlib.Path({str(created)!r})\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'create':\n"
                "    created.touch()\n"
                "    raise SystemExit(0)\n"
                "if len(sys.argv) > 1 and sys.argv[1] == 'run' and created.exists():\n"
                f"    print({str(Path(sys.executable).resolve())!r})\n"
                "    raise SystemExit(0)\n"
                "raise SystemExit(1)\n",
            )
            env = os.environ.copy()
            env["CONDA_EXE"] = str(manager)
            env.pop("VIBE_PYTHON", None)
            result = subprocess.run(
                [
                    sys.executable, str(BOOTSTRAP),
                    "--config-home", str(home),
                    "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                    "--print-python",
                ],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(created.is_file(), result.stdout)
            self.assertEqual((home / "vibe-python").read_text(encoding="utf-8").strip(), str(Path(sys.executable).resolve()))

    def test_bootstrap_repairs_configured_interpreter_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            home.mkdir(parents=True)
            marker = workspace / "pip-ran"
            interpreter = write_fake_interpreter(workspace, "configured-python", marker)
            config = home / "vibe-python"
            config.write_text(str(interpreter) + "\n", encoding="utf-8")
            env = os.environ.copy()
            env.pop("VIBE_PYTHON", None)
            env.pop("VIBE_PYTHON_REPAIR", None)
            env["FAKE_PYTHON_IDENTITY"] = str(interpreter)
            env["CONDA_EXE"] = str(write_test_executable(workspace, "conda-broken", "raise SystemExit(1)\n"))

            result = subprocess.run(
                [
                    sys.executable, str(BOOTSTRAP),
                    "--config-home", str(home),
                    "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                    "--print-python",
                ],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(marker.is_file(), result.stdout)
            self.assertIn("configured interpreter", result.stdout)
            self.assertEqual(
                Path(config.read_text(encoding="utf-8").strip()).resolve(),
                Path(interpreter).resolve(),
                result.stdout,
            )

    def test_bootstrap_switches_environment_only_when_explicitly_opted_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            home.mkdir(parents=True)
            marker = workspace / "pip-ran"
            interpreter = write_fake_interpreter(workspace, "configured-python", marker, pip_succeeds=False)
            config = home / "vibe-python"
            config.write_text(str(interpreter) + "\n", encoding="utf-8")
            created = workspace / "created"
            manager = write_fake_conda(workspace, "conda", created)

            def bootstrap(extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
                env = os.environ.copy()
                env.pop("VIBE_PYTHON", None)
                env.pop("VIBE_PYTHON_REPAIR", None)
                env["FAKE_PYTHON_IDENTITY"] = str(interpreter)
                env["CONDA_EXE"] = str(manager)
                env.update(extra_env)
                return subprocess.run(
                    [
                        sys.executable, str(BOOTSTRAP),
                        "--config-home", str(home),
                        "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                        "--print-python",
                    ],
                    env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                )

            refused = bootstrap({})
            self.assertNotEqual(refused.returncode, 0, refused.stdout)
            self.assertIn("VIBE_PYTHON_REPAIR", refused.stdout)
            self.assertFalse(created.is_file(), refused.stdout)
            self.assertEqual(
                Path(config.read_text(encoding="utf-8").strip()).resolve(),
                Path(interpreter).resolve(),
                refused.stdout,
            )

            opted_in = bootstrap({"VIBE_PYTHON_REPAIR": "1"})
            self.assertEqual(opted_in.returncode, 0, opted_in.stdout)
            self.assertTrue(created.is_file(), opted_in.stdout)
            self.assertEqual(
                Path(config.read_text(encoding="utf-8").strip()).resolve(),
                Path(sys.executable).resolve(),
                opted_in.stdout,
            )

    def test_bootstrap_refuses_to_rewrite_while_vibe_python_env_var_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            home.mkdir(parents=True)
            marker = workspace / "pip-ran"
            interpreter = write_fake_interpreter(workspace, "env-python", marker, pip_succeeds=False)
            config = home / "vibe-python"
            config.write_text(str(workspace / "untouched") + "\n", encoding="utf-8")
            created = workspace / "created"
            env = os.environ.copy()
            env["VIBE_PYTHON"] = str(interpreter)
            env["VIBE_PYTHON_REPAIR"] = "1"
            env["FAKE_PYTHON_IDENTITY"] = str(interpreter)
            env["CONDA_EXE"] = str(write_fake_conda(workspace, "conda", created))

            result = subprocess.run(
                [
                    sys.executable, str(BOOTSTRAP),
                    "--config-home", str(home),
                    "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                    "--print-python",
                ],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("Unset VIBE_PYTHON", result.stdout)
            self.assertNotIn("switching to Conda environment", result.stdout)
            self.assertFalse(created.is_file(), result.stdout)
            self.assertEqual(config.read_text(encoding="utf-8"), str(workspace / "untouched") + "\n")

    def test_bootstrap_does_not_invent_an_environment_for_a_missing_configured_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            home.mkdir(parents=True)
            missing = workspace / "gone-python"
            config = home / "vibe-python"
            config.write_text(str(missing) + "\n", encoding="utf-8")
            created = workspace / "created"
            env = os.environ.copy()
            env.pop("VIBE_PYTHON", None)
            env.pop("VIBE_PYTHON_REPAIR", None)
            env["CONDA_EXE"] = str(write_fake_conda(workspace, "conda", created))

            result = subprocess.run(
                [
                    sys.executable, str(BOOTSTRAP),
                    "--config-home", str(home),
                    "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                    "--print-python",
                ],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse(created.is_file(), result.stdout)
            self.assertEqual(config.read_text(encoding="utf-8"), str(missing) + "\n")
            self.assertIn("VIBE_PYTHON_REPAIR=1", result.stdout)

    def test_bootstrap_does_not_treat_a_falsy_repair_value_as_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            home.mkdir(parents=True)
            marker = workspace / "pip-ran"
            interpreter = write_fake_interpreter(workspace, "configured-python", marker, pip_succeeds=False)
            config = home / "vibe-python"
            config.write_text(str(interpreter) + "\n", encoding="utf-8")
            created = workspace / "created"
            for value in ("0", "false", "no", "off", ""):
                env = os.environ.copy()
                env.pop("VIBE_PYTHON", None)
                env["VIBE_PYTHON_REPAIR"] = value
                env["FAKE_PYTHON_IDENTITY"] = str(interpreter)
                env["CONDA_EXE"] = str(write_fake_conda(workspace, "conda", created))

                result = subprocess.run(
                    [
                        sys.executable, str(BOOTSTRAP),
                        "--config-home", str(home),
                        "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                        "--print-python",
                    ],
                    env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                )

                self.assertNotEqual(result.returncode, 0, f"value={value!r}\n{result.stdout}")
                self.assertFalse(created.is_file(), f"value={value!r}\n{result.stdout}")
                self.assertEqual(
                    Path(config.read_text(encoding="utf-8").strip()).resolve(),
                    Path(interpreter).resolve(),
                    f"value={value!r}\n{result.stdout}",
                )

    def test_bootstrap_opt_in_switches_when_the_configured_path_is_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            home.mkdir(parents=True)
            missing = workspace / "gone-python"
            config = home / "vibe-python"
            config.write_text(str(missing) + "\n", encoding="utf-8")
            created = workspace / "created"
            env = os.environ.copy()
            env.pop("VIBE_PYTHON", None)
            env["VIBE_PYTHON_REPAIR"] = "1"
            env["CONDA_EXE"] = str(write_fake_conda(workspace, "conda", created))

            result = subprocess.run(
                [
                    sys.executable, str(BOOTSTRAP),
                    "--config-home", str(home),
                    "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                    "--print-python",
                ],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(created.is_file(), result.stdout)
            self.assertEqual(
                Path(config.read_text(encoding="utf-8").strip()).resolve(),
                Path(sys.executable).resolve(),
                result.stdout,
            )

    def test_bootstrap_reports_the_vibe_python_source_for_a_blank_value(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            home.mkdir(parents=True)
            config = home / "vibe-python"
            config.write_text(str(workspace / "untouched") + "\n", encoding="utf-8")
            created = workspace / "created"
            env = os.environ.copy()
            env["VIBE_PYTHON"] = "   "
            env["VIBE_PYTHON_REPAIR"] = "1"
            env["CONDA_EXE"] = str(write_fake_conda(workspace, "conda", created))

            result = subprocess.run(
                [
                    sys.executable, str(BOOTSTRAP),
                    "--config-home", str(home),
                    "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                    "--print-python",
                ],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("Unset VIBE_PYTHON", result.stdout)
            self.assertFalse(created.is_file(), result.stdout)
            self.assertEqual(config.read_text(encoding="utf-8"), str(workspace / "untouched") + "\n")


class BootstrapInterpreterResolutionTests(unittest.TestCase):
    """reviewer-031 X3: a manager that exits 0 while printing an error is not a path."""

    def test_env_python_rejects_manager_error_text_with_zero_exit(self) -> None:
        bootstrap = load_bootstrap()
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            manager = write_test_executable(
                workspace,
                "conda-error-zero",
                "print('CommandNotFoundError: Your shell has not been properly configured')\n"
                "raise SystemExit(0)\n",
            )

            python, output = bootstrap.env_python(str(manager), "vibe-coding")

            self.assertIsNone(python, output)
            self.assertIn("CommandNotFoundError", output)

    def test_env_python_resolves_a_multi_line_manager_output(self) -> None:
        bootstrap = load_bootstrap()
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            manager = write_test_executable(
                workspace,
                "conda-chatty",
                "import sys\n"
                "print('WARNING: environment variables are not set')\n"
                f"print({str(Path(sys.executable).resolve())!r})\n"
                "raise SystemExit(0)\n",
            )

            python, _output = bootstrap.env_python(str(manager), "vibe-coding")

            self.assertEqual(python, str(Path(sys.executable).resolve()))

    def test_env_python_reports_a_missing_manager_without_raising(self) -> None:
        bootstrap = load_bootstrap()
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "no-such-conda"

            python, output = bootstrap.env_python(str(missing), "vibe-coding")

            self.assertIsNone(python)
            self.assertTrue(output.strip())

    def test_bootstrap_surfaces_manager_output_instead_of_a_spawn_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            home = workspace / "config-home"
            home.mkdir(parents=True)
            config = home / "vibe-python"
            config.write_text(str(workspace / "gone-python") + "\n", encoding="utf-8")
            manager = write_test_executable(
                workspace,
                "conda-error-zero",
                "print('CommandNotFoundError: Your shell has not been properly configured')\n"
                "raise SystemExit(0)\n",
            )
            env = os.environ.copy()
            env.pop("VIBE_PYTHON", None)
            env["VIBE_PYTHON_REPAIR"] = "1"
            env["CONDA_EXE"] = str(manager)

            result = subprocess.run(
                [
                    sys.executable, str(BOOTSTRAP),
                    "--config-home", str(home),
                    "--requirements", str(ROOT / "runtime/scripts/requirements.txt"),
                    "--print-python",
                ],
                env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("CommandNotFoundError", result.stdout)
            self.assertIn("did not print a usable interpreter path", result.stdout)
            self.assertNotIn("No such file or directory", result.stdout)
            self.assertEqual(config.read_text(encoding="utf-8"), str(workspace / "gone-python") + "\n")


if __name__ == "__main__":
    unittest.main()
