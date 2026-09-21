"""Explicit experimental project format and branch-local state selection."""
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
        raise ValueError("state_format_conflict: legacy writes are disabled; use vibe state-apply")


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
        if not isinstance(marker, dict) or set(marker) != {"format", "project_id", "experimental"}:
            raise ValueError("unsupported format marker fields")
        if type(marker["format"]) is not int or marker["format"] != 2 or marker["experimental"] is not True:
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
                raise StateError("git_context_error", "experimental state requires the Git worktree root")
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
    return Store(path, marker["project_id"], context_id)


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
    marker = {"format": 2, "project_id": uuid.uuid4().hex, "experimental": True}
    with (log / MARKER).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(marker, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    (log / ".gitignore").write_text(".state/\n", encoding="utf-8")
    exchange_directory = log / "exchange"
    exchange_directory.mkdir()
    (exchange_directory / ".gitattributes").write_text("* -text\n", encoding="utf-8")
    store = Store(directory / marker["project_id"] / context_id / "state.sqlite3", marker["project_id"], context_id)
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
    store = Store(path, marker["project_id"], context_id)
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
    state = open_store(root).status(limit=5)
    return (
        "Vibe transactional preview (read-only restore).\n"
        + json.dumps(state, ensure_ascii=True, separators=(",", ":"))
        + "\nUse explicit state-apply commands. Evidence/review completion gates and Git exchange "
        "are not yet enabled; implemented-unverified is not done. Do not initialize legacy state."
    )
