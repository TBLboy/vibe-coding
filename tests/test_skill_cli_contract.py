"""N02 (V3 PR-00): every command and record kind a Skill names must really exist.

Skills and Commands are instructions an executing agent follows literally. When one of
them names a CLI entry or a record kind that the store does not implement, the
instruction cannot be carried out: the agent either improvises (silently diverging from
the documented surface) or stops and asks.

This module walks the backticked ``vibe`` invocations in ``skills/**/SKILL.md`` and
``runtime/opencode/commands/*.md``, checks each against the real argparse surface
(including the ``--flags`` it mentions), and checks that every record kind a Skill names
exists in ``state_store.RECORD_KINDS``.

Both tests were marked ``expectedFailure`` for V3 PR-00, when ``a-business-clarify`` named
``vibe task create`` and the record kind ``open-question``, neither of which existed.
V3 PR-05 publishes both (``vibe goal create`` / ``vibe task create``, and a real
``open-question`` lifecycle), so the decorators are gone: the checks now guard the
contract rather than record a known defect.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "runtime" / "scripts"
VIBE = SCRIPTS / "vibe.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from state_store import RECORD_KINDS  # noqa: E402


# A backticked span that starts with the literal lowercase CLI name, e.g.
# `vibe task handoff --task-id TASK-1` or `vibe record create|update`.
INVOCATION = re.compile(
    r"`vibe\s+([a-z][a-z0-9-]*(?:\|[a-z][a-z0-9-]*)*)"
    r"(?:\s+([a-z][a-z0-9-]*(?:\|[a-z][a-z0-9-]*)*))?"
)
FLAG = re.compile(r"(--[a-z][a-z0-9-]*)")
# e.g. "record kinds `business-atom` / `open-question`"
RECORD_KIND_DECL = re.compile(r"record kinds?\s+((?:`[a-z][a-z0-9-]*`(?:\s*[/,]\s*)?)+)")


def instruction_sources() -> list[Path]:
    """Every file that tells an agent which CLI entries to run."""
    files = sorted((ROOT / "skills").glob("*/SKILL.md"))
    files += sorted((ROOT / "runtime" / "opencode" / "commands").glob("*.md"))
    return files


def help_output(parts: tuple[str, ...]) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, str(VIBE), *parts, "--help"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    return result.returncode, result.stdout


class SkillCliContractTests(unittest.TestCase):
    def test_skill_invocations_resolve_to_the_real_cli(self) -> None:
        offenders: list[str] = []
        for path in instruction_sources():
            relative = path.relative_to(ROOT).as_posix()
            for match in INVOCATION.finditer(path.read_text(encoding="utf-8")):
                head, tail = match.group(1), match.group(2)
                flags = FLAG.findall(match.group(0))
                candidates = (
                    [(head, item) for item in tail.split("|")] if tail else [(head,)]
                )
                for candidate in candidates:
                    code, output = help_output(candidate)
                    name = "vibe " + " ".join(candidate)
                    if code != 0:
                        offenders.append(f"{relative}: `{name}` is not a CLI entry")
                        continue
                    absent = [flag for flag in flags if flag not in output]
                    if absent:
                        offenders.append(f"{relative}: `{name}` does not accept {absent}")
        self.assertEqual(
            offenders, [],
            "Skills name CLI entries the command surface does not implement:\n  "
            + "\n  ".join(offenders),
        )

    def test_skill_record_kinds_exist(self) -> None:
        offenders: list[str] = []
        for path in instruction_sources():
            relative = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for match in RECORD_KIND_DECL.finditer(text):
                for kind in re.findall(r"`([a-z][a-z0-9-]*)`", match.group(1)):
                    if kind not in RECORD_KINDS:
                        offenders.append(f"{relative}: `{kind}` is not a record kind")
        self.assertEqual(
            offenders, [],
            "Skills name record kinds the store does not define:\n  " + "\n  ".join(offenders),
        )


    def test_task_create_without_a_goal_id_really_is_goal_less(self) -> None:
        """`--goal-id` is documented as omittable, so omitting it must work.

        The store's `task.create` shape requires the key — a null goal is a real
        choice, not a missing field — while the CLI dropped it whenever the flag was
        absent. The documented "omit for a goal-less task" path therefore failed with
        `payload has missing or unknown fields`.
        """
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            init = subprocess.run(
                [sys.executable, str(VIBE), "--root", str(project), "init"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(init.returncode, 0, init.stdout)
            created = subprocess.run(
                [sys.executable, str(VIBE), "--root", str(project), "task", "create",
                 "--id", "TASK-1", "--title", "Goal-less work"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(created.returncode, 0, created.stdout)
            shown = subprocess.run(
                [sys.executable, str(VIBE), "--root", str(project), "state-task", "TASK-1"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            self.assertEqual(shown.returncode, 0, shown.stdout)
            self.assertIsNone(json.loads(shown.stdout)["goal_id"])


if __name__ == "__main__":
    unittest.main()
