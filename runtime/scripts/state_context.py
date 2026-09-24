"""Transactional project format (format 2) and project-scoped state selection."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from state_store import StateError, Store


MARKER = "state-format.json"


def is_transactional(root: Path) -> bool:
    path = root / ".project-log" / MARKER
    private = root / ".project-log" / ".state"
    return path.exists() or path.is_symlink() or private.exists() or private.is_symlink()


def read_marker(root: Path) -> dict:
    path = root / ".project-log" / MARKER
    try:
        if path.stat().st_size > 4096:
            raise ValueError("oversized format marker")
        marker = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(marker, dict):
            raise ValueError("unsupported format marker fields")
        # Promoted format: {"format","project_id"}. Projects initialized while format 2
        # was experimental also carry experimental:true; it is read but never written.
        if set(marker) == {"format", "project_id", "experimental"}:
            if marker["experimental"] is not True:
                raise ValueError("unsupported state format")
        elif set(marker) != {"format", "project_id"}:
            raise ValueError("unsupported format marker fields")
        if type(marker["format"]) is not int or marker["format"] != 2:
            raise ValueError("unsupported state format")
        identifier = marker["project_id"]
        if not isinstance(identifier, str) or uuid.UUID(identifier).hex != identifier:
            raise ValueError("invalid project identity")
        return marker
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise StateError("invalid_format", str(exc)) from exc


def _git_marker(path: Path) -> Path | None:
    """Return ``path`` when it is a real Git marker, otherwise None.

    A normal repository uses a ``.git`` directory containing ``HEAD``; a linked
    worktree or submodule uses a ``.git`` file. Anything else - notably an empty
    ``.git`` directory left behind by an aborted ``git init`` - is not a
    repository and must not change how the work directory is identified.
    """
    try:
        if path.is_symlink() or not path.exists():
            return None
        if path.is_file():
            return path
        if path.is_dir() and (path / "HEAD").is_file():
            return path
    except OSError:
        return None
    return None


WORK_LAYOUT_CONTRACT = (
    "Project Log must live in a plain work folder: the work folder itself must not be a "
    "Git worktree root, and it must not sit inside another Git worktree.\n"
    "\n"
    "Expected:\n"
    "\n"
    "  work/                 a plain directory (no .git here)\n"
    "    .project-log/       a plain directory\n"
    "    repo-a/.git/        code repositories live below it\n"
    "    repo-b/.git/\n"
    "\n"
    "Remote durability comes from the knowledge-base archive, not from the work folder "
    "being a Git repository."
)


def detect_layout(root: Path) -> str:
    """Classify the work directory's layout.

    The only supported layout for a Project Log is a plain work folder: a directory
    that is neither a Git worktree root nor inside one. Code repositories live
    *below* it, and remote durability comes from the knowledge-base archive.

    Detection looks for a real ``.git`` marker rather than any directory named
    ``.git``, so an empty stray ``.git`` in an ancestor (a common accident in a home
    directory) does not turn the work directory into a false repository.
    """
    root = root.resolve()
    marker = next(
        (parent for parent in (root, *root.parents) if _git_marker(parent / ".git") is not None),
        None,
    )
    if marker is None:
        return "plain_work_folder"
    if marker == root:
        return "git_worktree_root"
    return "nested_in_git_worktree"


def git_context(root: Path) -> tuple[str, Path]:
    """Return the project-scoped state identity and the local state directory.

    A plain work folder is the only supported layout: the Project Log sits beside the
    code repositories and reaches Git through the knowledge-base archive. A Git
    worktree root, or a directory inside one, is rejected *before any write*, so
    ``vibe init`` cannot silently create a Project Log under an unsupported layout.

    The identity is deliberately branch-independent and path-only, so switching
    branches never hides or forks the log and moving a log between branches of the
    same work folder keeps the same store.
    """
    root = root.resolve()
    layout = detect_layout(root)
    if layout != "plain_work_folder":
        raise StateError("unsupported_work_layout", WORK_LAYOUT_CONTRACT)
    identity = {"root": str(root), "branch": "local"}
    directory = root / ".project-log" / ".state"
    context_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
    return context_id, directory


def open_store(root: Path, heal: bool = False) -> Store:
    """Open this worktree's store.

    ``heal=True`` first repairs a projection that lags the ledger, so a read
    cannot silently report a stale revision after a crash between the ledger
    fsync and the SQLite commit. It never rewrites the ledger: a store-ahead
    ledger is left for an explicit attach/export. Verification and portability
    reporting open the pure store so drift stays observable.
    """
    marker = read_marker(root)
    context_id, directory = git_context(root)
    path = directory / marker["project_id"] / context_id / "state.sqlite3"
    store = Store(path, marker["project_id"], context_id, root)
    if heal:
        store.heal_from_ledger()
    return store


def initialize(root: Path) -> Store:
    root = root.resolve()
    if not root.is_dir():
        raise StateError("invalid_root", "create the test project directory explicitly first")
    context_id, directory = git_context(root)
    log = root / ".project-log"
    try:
        log.mkdir()
    except FileExistsError as exc:
        raise StateError("existing_project_log", "refusing to overwrite an existing Project Log") from exc
    (log / ".state").mkdir()
    marker = {"format": 2, "project_id": uuid.uuid4().hex}
    with (log / MARKER).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(marker, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    (log / ".gitignore").write_text(".state/\n", encoding="utf-8")
    exchange_directory = log / "exchange"
    exchange_directory.mkdir()
    (exchange_directory / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    store = Store(
        directory / marker["project_id"] / context_id / "state.sqlite3",
        marker["project_id"],
        context_id,
        root,
    )
    store.initialize()
    return store


def attach(root: Path) -> Store:
    """Create or reconcile this worktree's local state database from the Git ledger.

    A clean clone has no local SQLite, so attach builds one and replays the whole
    ledger into it. If a local store already exists, it is reconciled instead:
    an identical projection is left alone, a stale projection is rebuilt, and
    ledger events the store has not seen are appended.
    """
    return attach_with_report(root)[0]


def attach_with_report(root: Path) -> tuple[Store, dict]:
    """Attach the worktree store and report how the ledger reconciliation went."""
    root = root.resolve()
    marker = read_marker(root)
    context_id, directory = git_context(root)
    path = directory / marker["project_id"] / context_id / "state.sqlite3"
    store = Store(path, marker["project_id"], context_id, root)
    if not (path.exists() or path.is_symlink()):
        store.initialize()
    # Reconcile in both directions: a fresh clone replays the ledger, a store
    # whose ledger was truncated/rolled back is re-exported, and a projection
    # that disagrees with replay is rebuilt whole.
    report = store.reconcile_with_ledger()
    if report["status"] == "in_sync" and report["revision"] == 0:
        report = {"status": "empty", "revision": 0, "appended": 0}
    return store, report


def apply_command(root: Path, envelope: dict) -> dict:
    store = open_store(root)
    receipt = store.apply(envelope)
    result = {"receipt": receipt, "projection": "pending", "exchange": "not-implemented"}
    try:
        from state_views import publish

        result["view"] = publish(store, store.path.parent / "generated")
        result["projection"] = "pending" if result["view"].get("projection_pending") else "published"
    except Exception as exc:
        result["projection_error"] = {"code": getattr(exc, "code", "projection_failed"), "message": str(exc)}
    return result


def refresh_views(root: Path) -> dict:
    from state_views import publish

    store = open_store(root, heal=True)
    return publish(store, store.path.parent / "generated")


def refresh_evidence(root: Path, reason: str | None = None, changed_paths=None) -> dict:
    """Invalidate active evidence whose recorded covered bytes changed."""
    store = open_store(root, heal=True)
    stale = store.stale_evidence(root)
    if changed_paths is not None:
        normalized = set()
        for value in changed_paths:
            if not isinstance(value, str) or not value.strip():
                continue
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = root / candidate
            try:
                normalized.add(candidate.resolve().relative_to(root.resolve()).as_posix())
            except ValueError:
                normalized.add(candidate.resolve().as_posix())
        covered_by_id = {
            entry["id"]: set(entry.get("covers", {}).get("files", []))
            for entry in store.list_evidence()
        }
        stale = [
            item for item in stale
            if normalized.intersection(covered_by_id.get(item["id"], set()))
        ]
    invalidated = []
    for item in stale:
        envelope = {
            "schema_version": 1,
            "command_id": uuid.uuid4().hex,
            "expected_revision": store.status()["revision"],
            "action": "evidence.invalidate",
            "payload": {
                "id": item["id"],
                "reason": reason or "; ".join(item["reasons"]),
            },
        }
        store.apply(envelope)
        invalidated.append(item["id"])
    result = {
        "checked_stale": len(stale),
        "invalidated": invalidated,
        "status": "updated" if invalidated else "unchanged",
    }
    if invalidated:
        try:
            result["view"] = refresh_views(root)
        except Exception as exc:
            result["projection_error"] = {
                "code": getattr(exc, "code", "projection_failed"),
                "message": str(exc),
            }
    return result


def publish_snapshot(root: Path) -> dict:
    from state_exchange import publish

    store = open_store(root)
    result = publish(store, root)
    try:
        result["view"] = refresh_views(root)
        result["projection"] = "published"
    except Exception as exc:
        result["projection_error"] = {"code": getattr(exc, "code", "projection_failed"), "message": str(exc)}
    return result


def import_snapshot(root: Path) -> dict:
    from state_exchange import import_snapshot as apply_snapshot

    store = open_store(root)
    result = apply_snapshot(store, root)
    try:
        result["view"] = refresh_views(root)
        result["projection"] = "published"
    except Exception as exc:
        result["projection_error"] = {"code": getattr(exc, "code", "projection_failed"), "message": str(exc)}
    return result


def exchange_status(root: Path) -> dict:
    from state_exchange import status

    return status(open_store(root), root)


def acknowledge_export(root: Path) -> dict:
    from state_exchange import acknowledge_export as confirm

    return confirm(open_store(root), root)


def abandon_export(root: Path, reason: str) -> dict:
    return {"status": "abandoned", "exchange": open_store(root).abandon_export(reason)}


def compact_context(root: Path) -> str:
    store = open_store(root, heal=True)
    state = store.status(limit=5)
    task = state.get("current_task") or state.get("latest_task")
    try:
        goal = store.get_goal(store.active_goal_id())
        goal_label = goal["id"]
    except StateError:
        goal = None
        active = store.active_goal_ids()
        # A second active goal turns the default target into a guess; surface the
        # ambiguity here instead of letting the session believe one of them.
        goal_label = (
            f"ambiguous ({', '.join(active)}); pass an explicit goal id"
            if len(active) > 1 else "-"
        )
    evidence = store.list_evidence()
    counts = {
        name: sum(item["status"] == name for item in evidence)
        for name in ("candidate", "valid", "failed", "stale", "superseded", "invalid")
    }
    lines = [
        "Vibe transactional context (read-only restore).",
        f"Project: {state['project_id']}",
        f"Revision: {state['revision']}",
        f"Project goal: {goal_label}",
        f"Run status: {(state.get('current_run') or state.get('latest_run') or {}).get('status', '-')}",
        f"Task: {task['id'] if task else '-'} [{task['status'] if task else '-'}]",
        f"Next action: {task.get('next_action') if task and task.get('next_action') else '-'}",
        "Evidence: " + ", ".join(f"{name}={counts[name]}" for name in counts),
    ]
    if task and task.get("blocker"):
        blocker = task["blocker"]
        lines.append(
            f"Blocker: {blocker['kind']} / {blocker['reason']} / resume when: {blocker['resume_when']}"
        )
    lines.append(
        "Completion requires valid evidence; high-risk work also requires an independent go review. "
        "Use the formal vibe command surface; the Project Log is the transactional format 2 store."
    )
    return "\n".join(lines) + "\n"
