"""TASK-058: archiving merges the ledger instead of replacing the KB copy."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "a-project-log-archive" / "scripts" / "archive.py"
LEDGER_RELATIVE = Path("ledger") / "v1" / "ledger.jsonl"


def load_archive_module():
    spec = importlib.util.spec_from_file_location("archive_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archive_module = load_archive_module()


def event(command_id: str, action: str = "goal.create") -> dict:
    return {
        "schema_version": 1, "command_id": command_id, "origin_kind": "local",
        "origin_context_id": "c" * 64, "origin_revision": 1, "action": action,
        "request": {"command_id": command_id}, "request_hash": "h",
        "receipt": {"command_id": command_id}, "created_at": "2026-01-01T00:00:00+00:00",
        "previous_hash": "", "event_hash": command_id,
    }


def write_ledger(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in events),
        encoding="utf-8",
    )


def read_ledger(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ArchiveSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.kb = self.base / "kb"
        (self.kb / "工程记录").mkdir(parents=True)
        self.remote = self.base / "kb-remote.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", str(self.kb)], check=True)
        for arguments in (
            ("config", "user.email", "kb@example.invalid"),
            ("config", "user.name", "KB"),
        ):
            subprocess.run(["git", "-C", str(self.kb), *arguments], check=True)
        subprocess.run(["git", "-C", str(self.kb), "remote", "add", "origin", str(self.remote)], check=True)
        (self.kb / "README.md").write_text("kb\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.kb), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(self.kb), "commit", "-qm", "init"], check=True)
        subprocess.run(
            ["git", "-C", str(self.kb), "push", "-q", "-u", "origin", "HEAD"], check=True,
        )

        self.work = self.base / "work"
        self.log = self.work / ".project-log"
        self.log.mkdir(parents=True)
        self.project_id = uuid.uuid4().hex
        (self.log / "state-format.json").write_text(
            json.dumps({"format": 2, "project_id": self.project_id}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self.events = [event("a" * 32), event("b" * 32)]
        write_ledger(self.log / LEDGER_RELATIVE, self.events)
        (self.log / ".state").mkdir()
        (self.log / ".state" / "state.sqlite3").write_bytes(b"sqlite")
        (self.log / "legacy" / "new-writes").mkdir(parents=True)
        (self.log / "legacy" / "new-writes" / "bundle.json").write_text("{}\n", encoding="utf-8")
        (self.log / "docs").mkdir()
        (self.log / "docs" / "note.md").write_text("hello\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def archive(self, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(self.work), "--kb", str(self.kb)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            env=None if env is None else {**os.environ, **env},
        )

    def commits(self) -> int:
        completed = subprocess.run(
            ["git", "-C", str(self.kb), "rev-list", "--count", "HEAD"],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        return int(completed.stdout.strip())

    @property
    def archived(self) -> Path:
        return self.kb / "工程记录" / "work" / ".project-log"

    def test_archive_copies_the_ledger_and_excludes_local_state(self) -> None:
        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.archived / "state-format.json").is_file())
        self.assertEqual(read_ledger(self.archived / LEDGER_RELATIVE), self.events)
        self.assertFalse((self.archived / ".state").exists())
        self.assertFalse((self.archived / "legacy" / "new-writes").exists())
        self.assertTrue((self.archived / "docs" / "note.md").is_file())

    def test_archiving_twice_is_idempotent(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.commits(), before)
        self.assertIn("no-changes", result.stdout)

    def test_archive_appends_only_the_new_tail(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        self.events.append(event("c" * 32, "task.create"))
        write_ledger(self.log / LEDGER_RELATIVE, self.events)

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read_ledger(self.archived / LEDGER_RELATIVE), self.events)
        self.assertIn('"appended": 1', result.stdout)

    def test_archive_refuses_when_the_knowledge_base_is_ahead(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        # The KB learns about a command the local ledger never saw.
        write_ledger(self.archived / LEDGER_RELATIVE, self.events + [event("d" * 32)])

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("align-project-progress", result.stderr)

    def test_archive_refuses_a_project_id_collision(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        (self.archived / "state-format.json").write_text(
            json.dumps({"format": 2, "project_id": "f" * 32}, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("project id mismatch", result.stderr)

    def test_archive_uses_the_work_folder_name(self) -> None:
        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"project": "work"', result.stdout)
        self.assertTrue((self.kb / "工程记录" / "work").is_dir())

    # -- TASK-079: a silent archive must fail loudly ---------------------------------

    def ignore_project_logs(self) -> None:
        """Reproduce the knowledge base rule that hid every ledger archive."""
        (self.kb / ".gitignore").write_text(".project-log/\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.kb), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.kb), "commit", "-qm", "ignore project logs"], check=True
        )

    def remote_ledger(self) -> list[dict]:
        completed = subprocess.run(
            [
                "git", "--git-dir", str(self.remote), "show",
                f"HEAD:工程记录/work/.project-log/{LEDGER_RELATIVE.as_posix()}",
            ],
            text=True, stdout=subprocess.PIPE, check=True,
        )
        return [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]

    def remote_has_ledger(self) -> bool:
        completed = subprocess.run(
            [
                "git", "--git-dir", str(self.remote), "cat-file", "-e",
                f"HEAD:工程记录/work/.project-log/{LEDGER_RELATIVE.as_posix()}",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        return completed.returncode == 0

    def test_archive_publishes_new_events_to_the_remote(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        self.events.append(event("c" * 32, "task.create"))
        write_ledger(self.log / LEDGER_RELATIVE, self.events)

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_ledger(), self.events)

    def test_archive_refuses_when_the_ledger_is_ignored(self) -> None:
        self.ignore_project_logs()
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("ignores the archived ledger", result.stderr)
        self.assertIn("!工程记录/work/.project-log/", result.stderr)
        self.assertEqual(self.commits(), before)

    def test_archive_accepts_an_ignored_but_already_tracked_ledger(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        self.ignore_project_logs()
        # Publish the new ignore rule so the branch and its remote agree; this test is
        # about the ignore rule, not about an archive that owes the remote a push.
        subprocess.run(["git", "-C", str(self.kb), "push", "-q"], check=True)

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no-changes", result.stdout)

    def ignore_project_logs_with_negations(self) -> None:
        """The corrected rule: the excluded directory itself is re-included."""
        (self.kb / ".gitignore").write_text(
            ".project-log/\n"
            "!工程记录/work/.project-log/\n"
            "!工程记录/work/.project-log/**\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.kb), "add", "-A"], check=True)
        subprocess.run(
            ["git", "-C", str(self.kb), "commit", "-qm", "ignore project logs with negations"],
            check=True,
        )

    def test_archive_accepts_a_negated_untracked_ledger(self) -> None:
        """A negation re-includes the ledger; check-ignore -v alone misreads it as excluded."""
        self.ignore_project_logs_with_negations()
        relative = "工程记录/work/.project-log/ledger/v1/ledger.jsonl"
        self.assertIsNone(archive_module.ignored_rule(self.kb, relative))

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_ledger(), self.events)

    def test_ignored_rule_reports_a_real_exclusion(self) -> None:
        self.ignore_project_logs()
        relative = "工程记录/work/.project-log/ledger/v1/ledger.jsonl"

        rule = archive_module.ignored_rule(self.kb, relative)

        self.assertIsNotNone(rule)
        self.assertIn(".project-log/", rule)

    def test_run_git_passes_the_proxy_environment(self) -> None:
        with mock.patch.dict(
            os.environ, {"VIBE_GIT_PROXY": "http://127.0.0.1:10808"}, clear=True
        ):
            with mock.patch.object(archive_module.subprocess, "run") as run:
                run.return_value = subprocess.CompletedProcess([], 0, "", "")
                archive_module._run_git(["git", "--version"], capture_output=True)

        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["https_proxy"], "http://127.0.0.1:10808")
        self.assertEqual(environment["HTTP_PROXY"], "http://127.0.0.1:10808")

    def test_git_environment_keeps_an_inherited_proxy(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "VIBE_GIT_PROXY": "http://configured.invalid",
                "http_proxy": "http://inherited.invalid",
            },
            clear=True,
        ):
            environment = archive_module.git_environment()

        self.assertEqual(environment["http_proxy"], "http://inherited.invalid")
        self.assertEqual(environment["https_proxy"], "http://configured.invalid")

    def test_configured_proxy_reads_a_config_file(self) -> None:
        config = self.base / "git_proxy.conf"
        config.write_text("http://127.0.0.1:10808\n", encoding="utf-8")

        with mock.patch.dict(os.environ, {"VIBE_GIT_PROXY": ""}, clear=True):
            self.assertEqual(
                archive_module.configured_proxy(config), "http://127.0.0.1:10808"
            )

    def test_configured_proxy_ignores_the_placeholder(self) -> None:
        config = self.base / "git_proxy.conf"
        config.write_text("__UNSET__\n", encoding="utf-8")

        with mock.patch.dict(os.environ, {"VIBE_GIT_PROXY": ""}, clear=True):
            self.assertEqual(archive_module.configured_proxy(config), "")

    def test_configured_proxy_skips_comments_and_blank_lines(self) -> None:
        config = self.base / "git_proxy.conf"
        config.write_text(
            "# a comment\n\n   \nhttp://127.0.0.1:10808\n", encoding="utf-8"
        )

        with mock.patch.dict(os.environ, {"VIBE_GIT_PROXY": ""}, clear=True):
            self.assertEqual(
                archive_module.configured_proxy(config), "http://127.0.0.1:10808"
            )

    def test_configured_proxy_lets_the_environment_override_the_file(self) -> None:
        config = self.base / "git_proxy.conf"
        config.write_text("http://from-file.invalid\n", encoding="utf-8")

        with mock.patch.dict(
            os.environ, {"VIBE_GIT_PROXY": "http://from-env.invalid"}, clear=True
        ):
            self.assertEqual(
                archive_module.configured_proxy(config), "http://from-env.invalid"
            )

    def test_shipped_proxy_example_is_copy_safe(self) -> None:
        """`cp git_proxy.conf.example git_proxy.conf` must not inject the comment block."""
        example = (
            ROOT / "skills" / "a-project-log-archive" / "scripts" / "git_proxy.conf.example"
        )
        self.assertTrue(example.is_file(), "the shipped proxy example is missing")

        with mock.patch.dict(os.environ, {"VIBE_GIT_PROXY": ""}, clear=True):
            self.assertEqual(archive_module.configured_proxy(example), "")

    def test_archive_refuses_when_the_index_ledger_is_stale(self) -> None:
        # A skip-worktree entry keeps the index ledger at the old revision while other
        # files still stage, so "something was committed" cannot prove the tail landed.
        self.assertEqual(self.archive().returncode, 0)
        subprocess.run(
            [
                "git", "-C", str(self.kb), "update-index", "--skip-worktree", "--",
                str(self.archived / LEDGER_RELATIVE),
            ],
            check=True,
        )
        self.events.append(event("c" * 32, "task.create"))
        write_ledger(self.log / LEDGER_RELATIVE, self.events)
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("not byte-identical", result.stderr)
        self.assertEqual(self.commits(), before)
        self.assertEqual(len(self.remote_ledger()), 2)

    def test_archive_reports_no_changes_when_the_worktree_ledger_was_restored(self) -> None:
        # The committed ledger already matches; restoring a deleted worktree copy is not
        # a new archive tail and must not be misreported as one.
        self.assertEqual(self.archive().returncode, 0)
        (self.archived / LEDGER_RELATIVE).unlink()

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no-changes", result.stdout)
        self.assertIn('"appended": 0', result.stdout)

    def test_archive_commit_excludes_unrelated_staged_files(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        (self.kb / "unrelated-secret.txt").write_text("secret\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.kb), "add", "--", "unrelated-secret.txt"], check=True
        )
        self.events.append(event("c" * 32, "task.create"))
        write_ledger(self.log / LEDGER_RELATIVE, self.events)

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        published = subprocess.run(
            ["git", "-C", str(self.kb), "show", "--name-only", "--pretty=format:", "HEAD"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.split()
        self.assertNotIn("unrelated-secret.txt", published)
        still_staged = subprocess.run(
            ["git", "-C", str(self.kb), "diff", "--cached", "--name-only"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertIn("unrelated-secret.txt", still_staged)

    def write_ledger_with_crlf(self) -> None:
        text = "".join(f"{json.dumps(item, ensure_ascii=False, sort_keys=True)}\r\n" for item in self.events)
        (self.log / LEDGER_RELATIVE).write_text(text, encoding="utf-8", newline="")

    def test_archive_refuses_a_clean_filter_that_rewrites_the_ledger(self) -> None:
        # hash-object applies clean filters, so hashing cannot prove the raw ledger
        # landed; only comparing raw blob bytes can.
        subprocess.run(
            ["git", "-C", str(self.kb), "config", "filter.drop.clean", "head -n 1"], check=True
        )
        (self.kb / ".gitattributes").write_text("*.jsonl filter=drop\n", encoding="utf-8")
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("not byte-identical", result.stderr)
        self.assertEqual(self.commits(), before)
        self.assertFalse(self.remote_has_ledger())

    def test_archive_refuses_end_of_line_normalisation(self) -> None:
        (self.kb / ".gitattributes").write_text("*.jsonl text=auto\n", encoding="utf-8")
        self.write_ledger_with_crlf()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("not byte-identical", result.stderr)

    def test_archive_accepts_no_conversion_attributes(self) -> None:
        (self.kb / ".gitattributes").write_text("*.jsonl -text\n", encoding="utf-8")
        self.write_ledger_with_crlf()

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        published = subprocess.run(
            ["git", "--git-dir", str(self.remote), "cat-file", "blob",
             "HEAD:工程记录/work/.project-log/ledger/v1/ledger.jsonl"],
            capture_output=True, check=True,
        ).stdout
        self.assertEqual(published, (self.log / LEDGER_RELATIVE).read_bytes())

    def test_archive_pushes_the_upstream_even_when_remote_push_config_diverges(self) -> None:
        # A bare `git push` obeys remote.<name>.push and can publish an unrelated ref.
        subprocess.run(["git", "-C", str(self.kb), "branch", "other"], check=True)
        subprocess.run(
            ["git", "-C", str(self.kb), "config", "remote.origin.push",
             "refs/heads/other:refs/heads/other"],
            check=True,
        )

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.remote_ledger(), self.events)
        published = subprocess.run(
            ["git", "--git-dir", str(self.remote), "rev-parse", "HEAD"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.strip()
        self.assertEqual(
            published, subprocess.run(
                ["git", "-C", str(self.kb), "rev-parse", "HEAD"],
                text=True, stdout=subprocess.PIPE, check=True,
            ).stdout.strip(),
        )

    def test_archive_detects_a_remote_that_rewrites_the_ref(self) -> None:
        hook = self.remote / "hooks" / "post-receive"
        hook.write_text(
            "#!/bin/sh\nwhile read old new ref; do\n"
            '  git update-ref -m "revert" "$ref" "$old" "$new"\ndone\n',
            encoding="utf-8",
        )
        hook.chmod(0o755)

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("did not reach", result.stderr)
        self.assertFalse(self.remote_has_ledger())

    def test_archive_pushes_a_commit_left_behind_by_a_failed_push(self) -> None:
        origin = subprocess.run(
            ["git", "-C", str(self.kb), "remote", "get-url", "origin"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(self.kb), "remote", "set-url", "origin",
             str(self.kb.parent / "missing-remote.git")],
            check=True,
        )

        failed = self.archive()

        self.assertEqual(failed.returncode, 1)
        self.assertGreater(self.commits(), 1)  # the commit is already local
        self.assertFalse(self.remote_has_ledger())

        subprocess.run(
            ["git", "-C", str(self.kb), "remote", "set-url", "origin", origin], check=True
        )
        recovered = self.archive()

        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertIn("pushed", recovered.stdout)
        self.assertEqual(self.remote_ledger(), self.events)

    def test_archive_refuses_a_branch_without_upstream(self) -> None:
        subprocess.run(["git", "-C", str(self.kb), "checkout", "-q", "-b", "local-only"], check=True)
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("has no upstream", result.stderr)
        self.assertEqual(self.commits(), before)

    def test_archive_refuses_a_self_referential_remote(self) -> None:
        # `git push . HEAD:refs/heads/x` and `git ls-remote .` both read this repository,
        # so pushing and verifying would be a self-satisfying loop.
        branch = subprocess.run(
            ["git", "-C", str(self.kb), "symbolic-ref", "--short", "HEAD"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "-C", str(self.kb), "config", f"branch.{branch}.remote", "."], check=True
        )
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("resolves to the knowledge base itself", result.stderr)
        self.assertEqual(self.commits(), before)
        self.assertFalse(self.remote_has_ledger())

    def point_upstream_at(self, url: str) -> None:
        branch = subprocess.run(
            ["git", "-C", str(self.kb), "symbolic-ref", "--short", "HEAD"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout.strip()
        added = subprocess.run(
            ["git", "-C", str(self.kb), "remote", "add", "probe", url],
            capture_output=True, check=False,
        )
        if added.returncode:
            subprocess.run(
                ["git", "-C", str(self.kb), "remote", "set-url", "probe", url], check=True
            )
        subprocess.run(
            ["git", "-C", str(self.kb), "config", f"branch.{branch}.remote", "probe"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.kb), "config", f"branch.{branch}.merge",
             "refs/heads/archive-target"],
            check=True,
        )

    def test_archive_refuses_a_file_url_to_itself(self) -> None:
        self.point_upstream_at(f"file://localhost{self.kb}")
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("resolves to the knowledge base itself", result.stderr)
        self.assertEqual(self.commits(), before)

    def test_archive_refuses_file_url_host_forms_that_name_itself(self) -> None:
        # Git's file transport opens the path component for any authority, so each of
        # these targets reaches the knowledge base itself. They must all fail closed:
        # reporting "pushed" while the real remote holds nothing is the failure this
        # guard exists to prevent.
        for authority in (
            "LOCALHOST",
            "localhost.",
            "127.0.0.1",
            "random.invalid",
            "localhost:123",
            "%6cocalhost",
        ):
            with self.subTest(authority=authority):
                self.point_upstream_at(f"file://{authority}{self.kb}")
                before = self.commits()

                result = self.archive()

                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertNotIn('"pushed"', result.stdout)
                self.assertEqual(self.commits(), before)
                self.assertFalse(self.remote_has_ledger())

    def test_archive_leaves_the_knowledge_base_clean_when_the_target_is_rejected(self) -> None:
        # Rejecting the publish target must not leave the copied 工程记录/ tree behind.
        self.point_upstream_at(f"file://random.invalid{self.kb}")

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        status = subprocess.run(
            ["git", "-C", str(self.kb), "status", "--porcelain"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        self.assertEqual(status, "")

    def test_archive_refuses_a_home_relative_path_to_itself(self) -> None:
        # Git expands `~`, so `~/kb` names $HOME/kb and can be the knowledge base itself.
        # The knowledge base lives at <temp>/kb, so HOME is pointed at <temp> here.
        self.point_upstream_at("~/kb")
        before = self.commits()

        result = self.archive(env={"HOME": str(self.base)})

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertNotIn('"pushed"', result.stdout)
        self.assertIn("resolves to the knowledge base itself", result.stderr)
        self.assertEqual(self.commits(), before)
        self.assertFalse(self.remote_has_ledger())

    def test_archive_refuses_an_unresolvable_home_relative_target(self) -> None:
        # `~user` that cannot be resolved must fail closed rather than be read as a
        # relative directory name that trivially is not the knowledge base.
        self.point_upstream_at("~vibe-no-such-user-9f3a/kb")
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertNotIn('"pushed"', result.stdout)
        self.assertEqual(self.commits(), before)
        self.assertFalse(self.remote_has_ledger())

    def test_archive_refuses_a_linked_worktree_of_itself(self) -> None:
        linked = self.kb.parent / "linked-worktree"
        subprocess.run(
            ["git", "-C", str(self.kb), "worktree", "add", "-q", "-b", "linked-wt",
             str(linked)],
            check=True,
        )
        self.point_upstream_at(str(linked))
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("resolves to the knowledge base itself", result.stderr)
        self.assertEqual(self.commits(), before)

    def test_archive_verifies_every_push_url(self) -> None:
        second = self.kb.parent / "kb-remote-2.git"
        subprocess.run(["git", "init", "-q", "--bare", str(second)], check=True)
        for url in (str(self.remote), str(second)):
            subprocess.run(
                ["git", "-C", str(self.kb), "remote", "set-url", "--add", "--push",
                 "origin", url],
                check=True,
            )

        result = self.archive()

        self.assertEqual(result.returncode, 0, result.stderr)
        for repository in (self.remote, second):
            published = subprocess.run(
                ["git", "--git-dir", str(repository), "cat-file", "blob",
                 "HEAD:工程记录/work/.project-log/ledger/v1/ledger.jsonl"],
                capture_output=True, check=True,
            ).stdout
            self.assertEqual(published, (self.log / LEDGER_RELATIVE).read_bytes())

    def test_archive_refuses_a_detached_head(self) -> None:
        subprocess.run(["git", "-C", str(self.kb), "checkout", "-q", "--detach"], check=True)
        before = self.commits()

        result = self.archive()

        self.assertEqual(result.returncode, 1)
        self.assertIn("not on a branch", result.stderr)
        self.assertEqual(self.commits(), before)

    def test_read_committed_ledger_rejects_invalid_utf8(self) -> None:
        self.assertEqual(self.archive().returncode, 0)
        (self.archived / LEDGER_RELATIVE).write_bytes(b"\xff\xfe not utf8\n")
        subprocess.run(
            ["git", "-C", str(self.kb), "add", "--",
             f"工程记录/work/.project-log/{LEDGER_RELATIVE.as_posix()}"],
            check=True,
        )
        subprocess.run(["git", "-C", str(self.kb), "commit", "-qm", "bad ledger"], check=True)

        with self.assertRaises(archive_module.ArchiveError) as caught:
            archive_module.read_committed_ledger(
                self.kb, "工程记录/work/.project-log/ledger/v1/ledger.jsonl"
            )

        self.assertIn("not valid UTF-8", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
