"""Transactional project format (format 2) and branch-local state selection."""
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


def reject_legacy(root: Path) -> None:
    if is_transactional(root):
        raise ValueError("state_format_conflict: legacy writes are disabled; use the formal vibe command surface")


def reject_legacy_path(path: Path) -> None:
    for candidate in (path.absolute(), path.resolve()):
        for parent in candidate.parents:
            if os.path.normcase(parent.name) == os.path.normcase(".project-log"):
                reject_legacy(parent.parent)
                break


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


def git_context(root: Path) -> tuple[str, Path]:
    root = root.resolve()
    repository_present = any((parent / ".git").exists() for parent in (root, *root.parents))
    if not repository_present:
        identity = {"root": str(root), "branch": "local"}
        directory = root / ".project-log" / ".state"
    else:
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}

        def git(*arguments: str, optional: bool = False) -> bytes:
            try:
                result = subprocess.run(
                    ["git", "-C", str(root), *arguments], env=environment,
                    capture_output=True, timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise StateError("git_context_error", str(exc)) from exc
            if result.returncode and not (optional and result.returncode == 1):
                raise StateError("git_context_error", result.stderr.decode("utf-8", errors="replace"))
            return result.stdout.rstrip(b"\r\n")

        try:
            top = Path(os.fsdecode(git("rev-parse", "--show-toplevel"))).resolve()
            if top != root:
                raise StateError("git_context_error", "format 2 state requires the Git worktree root")
            directory = Path(os.fsdecode(git("rev-parse", "--absolute-git-dir"))).resolve() / "vibe-state"
            branch = git("symbolic-ref", "--quiet", "HEAD", optional=True)
            if not branch:
                head = git("rev-parse", "--verify", "HEAD", optional=True)
                branch = b"detached:" + head if head else b"unborn"
            identity = {"root": str(root), "git_dir": str(directory), "branch_hex": branch.hex()}
        except UnicodeError as exc:
            raise StateError("git_context_error", "Git path encoding cannot be represented") from exc
    context_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
    return context_id, directory


def open_store(root: Path) -> Store:
    marker = read_marker(root)
    context_id, directory = git_context(root)
    path = directory / marker["project_id"] / context_id / "state.sqlite3"
    return Store(path, marker["project_id"], context_id, root)


def initialize(root: Path) -> Store:
    root = root.resolve()
    if not root.is_dir():
        raise StateError("invalid_root", "create the test project directory explicitly first")
    context_id, directory = git_context(root)
    log = root / ".project-log"
    try:
        log.mkdir()
    except FileExistsError as exc:
        raise StateError("migration_required", "refusing existing Project Log; migration is not available") from exc
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
    """Create this worktree's local state database for an existing format marker."""
    root = root.resolve()
    marker = read_marker(root)
    context_id, directory = git_context(root)
    path = directory / marker["project_id"] / context_id / "state.sqlite3"
    if path.exists() or path.is_symlink():
        raise StateError("store_exists", "This worktree context already has local state")
    store = Store(path, marker["project_id"], context_id, root)
    store.initialize()
    return store


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

    store = open_store(root)
    return publish(store, store.path.parent / "generated")


def refresh_evidence(root: Path, reason: str | None = None, changed_paths=None) -> dict:
    """Invalidate active evidence whose recorded covered bytes changed."""
    store = open_store(root)
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
    store = open_store(root)
    state = store.status(limit=5)
    task = state.get("current_task") or state.get("latest_task")
    try:
        goal = store.get_goal(store.active_goal_id())
    except StateError:
        goal = None
    evidence = store.list_evidence()
    counts = {
        name: sum(item["status"] == name for item in evidence)
        for name in ("candidate", "valid", "failed", "stale", "superseded", "invalid")
    }
    lines = [
        "Vibe transactional context (read-only restore).",
        f"Project: {state['project_id']}",
        f"Revision: {state['revision']}",
        f"Project goal: {goal['id'] if goal else '-'}",
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
        "Use the formal vibe command surface; do not initialize or write legacy YAML."
    )
    return "\n".join(lines) + "\n"
