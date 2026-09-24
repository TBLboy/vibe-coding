#!/usr/bin/env python3
"""Archive .project-log to the centralized knowledge base and push.

Archiving is a merge, never a replacement:

* The Git ledger is merged by ``command_id``: the knowledge base copy must already
  be an exact prefix of the local ledger, so only the new tail is ever added.
* ``.state/`` (the local SQLite cache), Git internals, ``.migration/`` scratch space
  and ``legacy/new-writes/`` rollback bundles are never copied.
* The project identity in ``state-format.json`` must match, so two unrelated
  projects that share a folder name can never silently overwrite each other.
* A silent archive is treated as a failure: the ledger staged in the knowledge base
  index must be byte-identical to the local ledger, so an ignored, skipped, or
  otherwise unstaged ledger can never be reported as archived.
* Re-running the archive is idempotent.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote, urlsplit


SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG = SKILL_DIR / "scripts" / "kb_path.conf"
PROXY_CONFIG = SKILL_DIR / "scripts" / "git_proxy.conf"
PLACEHOLDER = "__UNSET__"
LEDGER_RELATIVE = Path("ledger") / "v1" / "ledger.jsonl"
MARKER = "state-format.json"
# Machine-local or derivable: never archived.
EXCLUDED_NAMES = {".state", ".git", ".migration", "new-writes", "ledger"}
# Authorities a file:// push target may carry. Anything else is a form whose meaning
# depends on the platform, so it is refused rather than interpreted.
CANONICAL_FILE_AUTHORITIES = ("", "localhost")


class ArchiveError(RuntimeError):
    """A condition the operator must resolve before archiving can continue."""


def get_kb_base() -> Path:
    """Read the KB path from config, or report unconfigured."""
    if not CONFIG.exists():
        raise ArchiveError(
            f"CONFIG MISSING: {CONFIG} not found. Ask the user for the absolute path "
            "to their My_knowledge_base."
        )
    raw = CONFIG.read_text().strip()
    if raw == PLACEHOLDER or not raw:
        raise ArchiveError(
            f"CONFIG UNCONFIGURED: {CONFIG} contains the placeholder. Ask the user for "
            "the absolute path to their My_knowledge_base."
        )
    return Path(raw).expanduser()


def configured_proxy(config: Path | None = None) -> str:
    """The Git transport proxy for this machine, or an empty string when unset.

    ``VIBE_GIT_PROXY`` wins so a one-off run can override the persisted value; the
    ``git_proxy.conf`` file beside ``kb_path.conf`` keeps it for every later run. The
    file may carry ``#`` comments and blank lines, so copying the shipped example does
    not turn the whole comment block into a proxy URL; the first remaining line is it.
    """
    value = os.environ.get("VIBE_GIT_PROXY", "").strip()
    if value:
        return value
    path = PROXY_CONFIG if config is None else Path(config)
    if not path.is_file():
        return ""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ArchiveError(f"cannot read the Git proxy config {path}: {error}") from error
    for line in raw.splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        return "" if candidate == PLACEHOLDER else candidate
    return ""


def git_environment() -> dict[str, str]:
    """Environment for every Git subprocess, carrying the configured proxy.

    Git already honours ``http_proxy``/``https_proxy`` from the caller, so this only
    fills them in from the persisted configuration. An inherited value always wins,
    because the caller's own environment is the more specific choice.
    """
    environment = dict(os.environ)
    proxy = configured_proxy()
    if proxy:
        for name in (
            "http_proxy", "https_proxy", "all_proxy",
            "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        ):
            environment.setdefault(name, proxy)
    return environment


def _run_git(arguments: list[str], **options):
    """Run one Git command with the environment that carries the configured proxy."""
    return subprocess.run(arguments, env=git_environment(), **options)


def read_project_id(log: Path) -> str | None:
    """The project identity recorded in a Project Log marker, or None when absent."""
    marker = log / MARKER
    if not marker.is_file():
        return None
    try:
        document = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ArchiveError(f"{marker} is not readable JSON: {error}") from error
    if type(document) is not dict:
        raise ArchiveError(f"{marker} is not a JSON object")
    identifier = document.get("project_id")
    if identifier is not None and type(identifier) is not str:
        raise ArchiveError(f"{marker} has a non-string project_id")
    return identifier


def read_ledger(path: Path) -> list[dict]:
    """Parse a ledger file into its events, or an empty list when it is absent."""
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ArchiveError(f"cannot read ledger {path}: {error}") from error
    events: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise ArchiveError(f"{path}:{number} is not valid JSON: {error}") from error
        if type(event) is not dict or "command_id" not in event:
            raise ArchiveError(f"{path}:{number} is not a ledger event")
        events.append(event)
    return events


def compare_ledgers(local_events: list[dict], kb_events: list[dict]) -> dict:
    """Refuse unless the KB ledger is an exact prefix of the local ledger.

    Returns the event counts; the caller adds the tail length measured against the
    committed baseline.
    """
    if len(kb_events) > len(local_events):
        raise ArchiveError(
            f"the knowledge base ledger holds {len(kb_events)} commands but the local "
            f"ledger holds {len(local_events)}; run the align-project-progress skill "
            "before archiving so the two histories are merged first"
        )
    if local_events[: len(kb_events)] != kb_events:
        shared = {
            event["command_id"] for event in kb_events
        } & {
            event["command_id"] for event in local_events
        }
        raise ArchiveError(
            "the knowledge base ledger diverges from the local ledger; refusing to "
            f"archive over {len(shared)} shared command(s). Compare the two ledger files."
        )
    return {
        "local_events": len(local_events),
        "kb_events": len(kb_events),
    }


def read_committed_ledger(kb_root: Path, ledger_relative: str) -> list[dict]:
    """Read the ledger as committed at HEAD, or an empty list when HEAD has none."""
    raw = blob_bytes(kb_root, f"HEAD:{ledger_relative}")
    if raw is None:
        return []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ArchiveError(f"HEAD:{ledger_relative} is not valid UTF-8: {error}") from error
    events: list[dict] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError as error:
            raise ArchiveError(
                f"HEAD:{ledger_relative}:{number} is not valid JSON: {error}"
            ) from error
        if type(event) is not dict or "command_id" not in event:
            raise ArchiveError(f"HEAD:{ledger_relative}:{number} is not a ledger event")
        events.append(event)
    return events


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDED_NAMES}


def copy_project_log(src: Path, dst: Path) -> dict:
    """Merge the local Project Log into the KB copy, ledger included, without deleting."""
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)
    ledger_source = src / LEDGER_RELATIVE
    if ledger_source.is_file():
        ledger_target = dst / LEDGER_RELATIVE
        ledger_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ledger_source, ledger_target)
    return {
        "files": sum(1 for item in dst.rglob("*") if item.is_file()),
        "ledger": str(dst / LEDGER_RELATIVE),
    }


def ignored_rule(kb_root: Path, relative: str) -> str | None:
    """Return the .gitignore rule that excludes ``relative``, or None when it is reachable.

    A tracked file reaches the remote regardless of ignore rules, so tracking status is
    checked first. The verdict for an untracked path comes from ``check-ignore -q``:
    ``check-ignore -v`` exits 0 whenever *any* rule matches, including a ``!`` negation
    that re-includes the path, so its exit status alone would report a correctly negated
    path as excluded. ``-v`` is consulted afterwards only to name the matching rule.
    """
    tracked = _run_git(
        ["git", "-C", str(kb_root), "ls-files", "--error-unmatch", "--", relative],
        capture_output=True, text=True, check=False,
    )
    if tracked.returncode == 0:
        return None
    if tracked.returncode != 1:
        # Only exit status 1 means "not tracked"; anything else means Git could not
        # answer, which must not be mistaken for a healthy path.
        raise ArchiveError(
            f"cannot inspect the knowledge base repository at {kb_root}: "
            f"{tracked.stderr.strip() or 'git ls-files failed'}"
        )
    verdict = _run_git(
        ["git", "-C", str(kb_root), "check-ignore", "-q", "--", relative],
        capture_output=True, text=True, check=False,
    )
    if verdict.returncode == 1:
        return None
    if verdict.returncode != 0:
        # 0 means "ignored", 1 means "not ignored"; any other status means the probe
        # failed, so fail closed instead of assuming the ledger is reachable.
        raise ArchiveError(
            f"cannot determine whether {relative} is ignored by {kb_root}: "
            f"{verdict.stderr.strip() or 'git check-ignore failed'}"
        )
    probe = _run_git(
        ["git", "-C", str(kb_root), "check-ignore", "-v", "--", relative],
        capture_output=True, text=True, check=False,
    )
    return probe.stdout.strip() or "(matched an ignore rule)"


def blob_bytes(kb_root: Path, revision: str) -> bytes | None:
    """Raw bytes of a Git blob (``:path`` for the index, ``HEAD:path`` for the commit).

    ``git cat-file blob`` returns what Git actually stores, after any clean filter or
    end-of-line conversion, which is exactly what the remote would receive.
    """
    probe = _run_git(
        ["git", "-C", str(kb_root), "cat-file", "blob", revision],
        capture_output=True, check=False,
    )
    if probe.returncode:
        return None
    return probe.stdout


def revision(kb_root: Path, name: str) -> str | None:
    """Resolve a revision to a full object name, or None when Git cannot."""
    probe = _run_git(
        ["git", "-C", str(kb_root), "rev-parse", name],
        capture_output=True, text=True, check=False,
    )
    if probe.returncode:
        return None
    return probe.stdout.strip() or None


def config_value(kb_root: Path, key: str) -> str:
    probe = _run_git(
        ["git", "-C", str(kb_root), "config", "--get", key],
        capture_output=True, text=True, check=False,
    )
    return probe.stdout.strip() if probe.returncode == 0 else ""


def repository_identity(path: Path) -> str | None:
    """Repository identity shared by every worktree of ``path``, or None.

    Linked worktrees have distinct git directories but one common directory, so the
    common directory is what decides whether a push target is really this repository.
    """
    for arguments in (
        ("rev-parse", "--path-format=absolute", "--git-common-dir"),
        # Older Git has no --path-format; --git-common-dir alone still names the shared
        # directory of a linked worktree, unlike --absolute-git-dir which names the
        # worktree's own git dir and would make the same repository look different.
        ("rev-parse", "--git-common-dir"),
    ):
        probe = _run_git(
            ["git", "-C", str(path), *arguments],
            capture_output=True, text=True, check=False,
        )
        if probe.returncode:
            continue
        value = probe.stdout.strip()
        if not value:
            continue
        resolved = Path(value)
        if not resolved.is_absolute():
            resolved = path / resolved
        return str(resolved.resolve())
    return None


def local_path_of(target: str) -> Path | None:
    """Filesystem path a push target names, or None when it is not a local path.

    Git's ``file://`` transport opens the *path* component, whatever the authority says,
    so ``file://random.invalid/tmp/kb`` reads ``/tmp/kb`` just like ``file:///tmp/kb``.
    The path is therefore what must be compared against the knowledge base.

    Git also expands a leading ``~`` in a plain local target, exactly like a shell, so
    ``~/kb`` names ``$HOME/kb`` and must be compared after expansion. A ``~user`` that
    cannot be resolved is reported instead of being treated as a relative directory name
    that could not possibly be the knowledge base.
    """
    parsed = urlsplit(target)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme:
        return None
    if "@" in target.split("/", 1)[0] and ":" in target:
        return None  # scp-like ssh target, for example git@github.com:owner/repo.git
    try:
        return Path(target).expanduser()
    except RuntimeError as error:
        raise ArchiveError(
            f"the archive target {target!r} starts with '~' but the home directory it "
            "names cannot be resolved, so the archive cannot prove it is not the "
            "knowledge base itself; refusing to run. Use an absolute path instead."
        ) from error


def reject_self_reference(kb_root: Path, target: str) -> None:
    """Refuse a push target that resolves to the knowledge base repository itself.

    ``git push . HEAD:refs/heads/x`` and ``git ls-remote .`` both read the local
    repository, so pushing and then verifying would be a self-satisfying loop that
    proves nothing about any remote.

    ``file://`` URLs carrying a host component are refused outright: git accepts forms
    such as ``file://localhost./``, ``file://127.0.0.1/``, ``file://random.invalid/``,
    ``file://localhost:123/`` and ``file://%6cocalhost/`` and still opens a local path,
    but the rendering is platform- and version-dependent, so the archive cannot prove a
    non-self target here and fails closed instead of guessing.

    Local targets are compared after ``~`` expansion because ``git push ~/kb`` and
    ``git ls-remote ~/kb`` read ``$HOME/kb``; a ``~`` that survives expansion is treated
    as unverifiable rather than as a directory literally named ``~``.
    """
    parsed = urlsplit(target)
    if parsed.scheme == "file" and parsed.netloc.lower() not in CANONICAL_FILE_AUTHORITIES:
        raise ArchiveError(
            f"the archive target {target!r} is a file:// URL with a host component "
            f"({parsed.netloc!r}). Git resolves such a target differently per platform, "
            "so the archive cannot prove it is not the knowledge base itself and refuses "
            "to run. Use a plain path, file:///absolute/path, or "
            "file://localhost/absolute/path instead."
        )
    candidate = local_path_of(target)
    if candidate is None:
        return
    if str(candidate) == "~" or str(candidate).startswith("~/"):
        raise ArchiveError(
            f"the archive target {target!r} names a home directory that could not be "
            "expanded, so the archive cannot prove it is not the knowledge base itself; "
            "refusing to run. Use an absolute path instead."
        )
    path = candidate
    if not path.is_absolute():
        path = kb_root / path
    path = path.resolve()
    if not path.exists():
        return
    identity = repository_identity(path)
    own = repository_identity(kb_root)
    if identity is not None and own is not None and identity == own:
        raise ArchiveError(
            f"the archive target {target!r} resolves to the knowledge base itself; pushing "
            "and verifying against the same repository would prove nothing, so the archive "
            "refuses to run"
        )


def push_urls(kb_root: Path, remote: str) -> list[str]:
    """Every URL ``git push <remote>`` would contact, in order."""
    probe = _run_git(
        ["git", "-C", str(kb_root), "remote", "get-url", "--push", "--all", remote],
        capture_output=True, text=True, check=False,
    )
    if probe.returncode:
        reject_self_reference(kb_root, remote)
        raise ArchiveError(
            f"cannot resolve the push URL(s) of remote {remote!r} in {kb_root}: "
            f"{probe.stderr.strip() or 'git remote get-url failed'}"
        )
    urls = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
    if not urls:
        raise ArchiveError(f"remote {remote!r} in {kb_root} has no push URL")
    for url in urls:
        reject_self_reference(kb_root, url)
    return urls


def push_target(kb_root: Path) -> tuple[str, str, list[str]]:
    """Resolve the single remote, ref, and push URLs this archive may publish to.

    A bare ``git push`` obeys ``remote.<name>.push`` and ``push.default``, so it can
    publish an unrelated ref while the archive commit stays local. The upstream of the
    checked-out branch is the only target, and it is resolved before anything is
    committed so a missing upstream cannot leave a stray commit behind.
    """
    branch = _run_git(
        ["git", "-C", str(kb_root), "symbolic-ref", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if branch.returncode:
        raise ArchiveError(
            f"{kb_root} is not on a branch, so the archive has no unambiguous push "
            "target; check out the archive branch before archiving"
        )
    name = branch.stdout.strip()
    remote = config_value(kb_root, f"branch.{name}.remote")
    ref = config_value(kb_root, f"branch.{name}.merge")
    if not remote or not ref:
        raise ArchiveError(
            f"branch {name} has no upstream in {kb_root}, so the archive cannot decide "
            f"where to publish. Set one first:\n  git -C {kb_root} push -u <remote> {name}"
        )
    return remote, ref, push_urls(kb_root, remote)


def remote_revision(kb_root: Path, remote: str, ref: str, attempts: int = 3) -> tuple[bool, str | None]:
    """``(probe_succeeded, revision)`` for ``ref`` on ``remote``.

    ``git ls-remote`` exit status 0 means matching refs were listed and 2 means the remote
    answered but holds no such ref. Any other status is a transport or configuration
    failure, which must not be mistaken for "the remote does not have the commit".
    """
    for attempt in range(attempts):
        probe = _run_git(
            ["git", "-C", str(kb_root), "ls-remote", "--exit-code", remote, ref],
            capture_output=True, text=True, check=False,
        )
        if probe.returncode in (0, 2):
            fields = probe.stdout.split()
            return True, fields[0] if fields else None
        if attempt + 1 < attempts:
            time.sleep(attempt + 1)
    return False, None


def push_and_verify(
    kb_root: Path, remote: str, remote_ref: str, commit: str, urls: list[str]
) -> None:
    """Push ``commit`` to the upstream ref and verify every URL it lands on."""
    pushed = _run_git(
        ["git", "-C", str(kb_root), "push", "--porcelain", remote, f"{commit}:{remote_ref}"],
        capture_output=True, text=True, check=False,
    )
    if pushed.returncode:
        detail = pushed.stderr.strip() or pushed.stdout.strip()
        raise ArchiveError(
            f"git push {remote} {commit[:12]}:{remote_ref} failed: {detail}\n"
            "if this is a network timeout, give the archive a Git transport proxy in "
            f"{PROXY_CONFIG} (a single URL) or in VIBE_GIT_PROXY, then re-run"
        )
    for url in urls:
        probed, reported = remote_revision(kb_root, url, remote_ref)
        if not probed:
            raise ArchiveError(
                f"the push to {url} reported success, but the remote ref could not be "
                "verified (network or credentials). Re-run the archive to confirm; a "
                f"completed push is not repeated and the commit {commit} is already local."
            )
        if reported != commit:
            raise ArchiveError(
                f"the archive commit did not reach {url} {remote_ref}: the remote reports "
                f"{reported or '<missing>'} but the archived revision is {commit}. "
                "Check for a remote hook that rewrites, rejects, or delays the ref update."
            )


def git_push(
    kb_root: Path,
    project_name: str,
    local_ledger: Path,
    target: tuple[str, str, list[str]] | None = None,
) -> str:
    """Stage, commit, and push only this project's archive directory.

    Staging alone cannot prove the log landed: ``skip-worktree``/``assume-unchanged``
    entries and ``.gitignore`` keep the index ledger stale while unrelated files still
    stage, and a clean filter can rewrite the ledger on the way into Git. Both the staged
    blob and the committed blob are therefore compared byte-for-byte against the local
    ledger, and the run refuses to push a commit whose ledger is not identical.

    ``target`` is the already-validated ``push_target`` result; callers pass it so an
    unusable upstream is rejected before the knowledge base worktree is modified.
    """
    relative = str(Path("工程记录") / project_name)
    ledger_relative = str(Path("工程记录") / project_name / ".project-log" / LEDGER_RELATIVE)
    remote, remote_ref, urls = target if target is not None else push_target(kb_root)
    rule = ignored_rule(kb_root, ledger_relative)
    if rule is not None:
        raise ArchiveError(
            "the knowledge base ignores the archived ledger, so the log history would "
            f"never reach the remote:\n  {rule}\n"
            "add negations for this project to the knowledge base .gitignore:\n"
            f"  !{Path('工程记录') / project_name}/.project-log/\n"
            f"  !{Path('工程记录') / project_name}/.project-log/**\n"
            "then re-run the archive"
        )
    completed = _run_git(
        ["git", "-C", str(kb_root), "add", "-A", "--", relative],
        capture_output=True, text=True, check=False,
    )
    if completed.returncode:
        raise ArchiveError(f"git add failed: {completed.stderr.strip()}")

    try:
        local_bytes = local_ledger.read_bytes()
    except OSError as error:
        raise ArchiveError(f"cannot read the local ledger {local_ledger}: {error}") from error

    staged_bytes = blob_bytes(kb_root, f":{ledger_relative}")
    if staged_bytes is None:
        raise ArchiveError(
            f"the knowledge base index does not hold {ledger_relative}, so the ledger "
            "would never reach the remote. Check that the knowledge base tracks the "
            "ledger:\n"
            f"  git -C {kb_root} check-ignore -v -- {ledger_relative}\n"
            f"  git -C {kb_root} ls-files --error-unmatch -- {ledger_relative}"
        )
    if staged_bytes != local_bytes:
        raise ArchiveError(
            "the staged ledger is not byte-identical to the local ledger, so the archive "
            "would publish altered log history. Common causes and fixes:\n"
            f"  git -C {kb_root} update-index --no-skip-worktree -- {ledger_relative}\n"
            f"  git -C {kb_root} update-index --no-assume-unchanged -- {ledger_relative}\n"
            f"  # a clean filter or text/eol conversion on {ledger_relative} must be removed"
        )

    pending = _run_git(
        ["git", "-C", str(kb_root), "diff", "--cached", "--quiet", "--", relative],
        check=False,
    )
    if pending.returncode == 0:
        # Nothing to commit, but an earlier run may have committed and then failed to
        # push. Reporting no-changes would leave the archive stranded locally forever.
        current = revision(kb_root, "HEAD")
        if current is not None:
            for url in urls:
                probed, reported = remote_revision(kb_root, url, remote_ref)
                if not probed:
                    raise ArchiveError(
                        f"cannot verify {url} {remote_ref}; the archive will not claim "
                        "success without confirming the remote holds the committed log"
                    )
                if reported != current:
                    push_and_verify(kb_root, remote, remote_ref, current, urls)
                    return "pushed"
        return "no-changes"
    if pending.returncode != 1:
        raise ArchiveError(
            "cannot inspect the staged archive; refusing to commit blindly. "
            f"Re-run: git -C {kb_root} diff --cached -- {relative}"
        )
    parent = revision(kb_root, "HEAD")
    committed = _run_git(
        [
            "git", "-C", str(kb_root), "commit", "--only", "-m",
            f"archive: {project_name}", "--", relative,
        ],
        capture_output=True, text=True, check=False,
    )
    if committed.returncode:
        raise ArchiveError(f"git commit failed: {committed.stderr.strip()}")
    archive_commit = revision(kb_root, "HEAD")
    head_bytes = blob_bytes(kb_root, f"HEAD:{ledger_relative}")
    if head_bytes != local_bytes:
        raise ArchiveError(
            "the committed ledger is not byte-identical to the local ledger; refusing to "
            "push. Inspect with:\n"
            f"  git -C {kb_root} log --oneline -2\n"
            f"  git -C {kb_root} cat-file blob HEAD:{ledger_relative}\n"
            f"If HEAD is still the archive commit, undo it with:\n"
            f"  git -C {kb_root} reset --soft {parent}\n"
            "(that reset is only safe while HEAD is the archive commit; it is now "
            f"{archive_commit})."
        )
    if revision(kb_root, "HEAD") != archive_commit:
        raise ArchiveError(
            "HEAD moved after the archive commit, so the revision that was verified is no "
            "longer the checked-out one; refusing to push"
        )
    push_and_verify(kb_root, remote, remote_ref, archive_commit, urls)
    return "pushed"


def archive(project_root: Path, kb_base: Path) -> dict:
    root = Path(project_root).resolve()
    source = root / ".project-log"
    if not source.is_dir():
        raise ArchiveError(f".project-log not found in {root}")
    engineering = Path(kb_base).expanduser() / "工程记录"
    if not engineering.is_dir():
        raise ArchiveError(f"工程记录/ not found under {kb_base}")

    # The project name is the work folder name, exactly as the user specified.
    project_name = root.name
    destination = engineering / project_name / ".project-log"

    local_id = read_project_id(source)
    known_id = read_project_id(destination)
    if local_id and known_id and local_id != known_id:
        raise ArchiveError(
            f"project id mismatch for {project_name}: local {local_id} vs knowledge base "
            f"{known_id}; refusing to overwrite an unrelated project"
        )
    if local_id is None and (destination / LEDGER_RELATIVE).is_file():
        raise ArchiveError(
            f"{source / MARKER} has no project_id but the knowledge base already holds a "
            "ledger for this name; refusing to archive"
        )

    local_events = read_ledger(source / LEDGER_RELATIVE)
    kb_events = read_ledger(destination / LEDGER_RELATIVE)
    ledger = compare_ledgers(local_events, kb_events)
    kb_root = Path(kb_base).expanduser()
    ledger_relative = str(
        Path("工程记录") / project_name / ".project-log" / LEDGER_RELATIVE
    )
    committed = read_committed_ledger(kb_root, ledger_relative)
    ledger["kb_committed"] = len(committed)
    ledger["appended"] = max(0, len(local_events) - len(committed))
    # Resolve the publish target before touching the knowledge base worktree: an
    # unusable upstream or a self-referential remote must not leave a half-written
    # 工程记录/ directory behind.
    target = push_target(kb_root)
    copied = copy_project_log(source, destination)
    pushed = git_push(kb_root, project_name, source / LEDGER_RELATIVE, target)
    return {
        "project": project_name,
        "project_id": local_id,
        "destination": str(destination),
        "ledger": ledger,
        "files": copied["files"],
        "git": pushed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive project log to knowledge base")
    parser.add_argument("--project-root", required=True, help="Path to project root")
    parser.add_argument("--kb", help="Knowledge base root; defaults to the configured path")
    args = parser.parse_args()
    try:
        kb_base = Path(args.kb) if args.kb else get_kb_base()
        report = archive(Path(args.project_root), kb_base)
    except ArchiveError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
