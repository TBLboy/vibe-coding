"""Explicit snapshot export and import under a short cooperating Git lock.

Ordinary task commands never take the Git index lock. Only an explicit
publication or import window does, and an interrupted window leaves a lock that
must be investigated by the operator rather than removed automatically.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import uuid

from state_store import SCHEMA_VERSION, StateError, Store


EXCHANGE_RELATIVE = Path(".project-log/exchange")
MANIFEST_FIELDS = {
    "schema_version", "project_id", "snapshot_id", "parent_id", "branch",
    "data_sha256", "exported_local_revision", "created_at",
}
MAX_OBJECT_BYTES = 32 * 1024 * 1024
SNAPSHOT_NAME = "current.json"
TEMP_SUFFIX = ".tmp-"


def _canonical(value) -> bytes:
    """Single-line canonical JSON.

    Snapshot objects are committed to Git, so they must survive line-ending
    normalization unchanged; a single line has no line ending to convert.
    """
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _normalized(content: bytes) -> bytes:
    return content.replace(b"\r\n", b"\n")


def _fingerprint(value) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _git(root: Path, *arguments: str, optional: bool = False) -> bytes:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments], env=environment, capture_output=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StateError("git_context_error", str(exc)) from exc
    if result.returncode:
        if optional:
            return b""
        raise StateError("git_context_error", result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout.rstrip(b"\r\n")


def _require_repository(root: Path) -> Path:
    git_directory = Path(os.fsdecode(_git(root, "rev-parse", "--absolute-git-dir"))).resolve()
    top = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel"))).resolve()
    if top != root.resolve():
        raise StateError("git_context_error", "explicit exchange requires the Git worktree root")
    return git_directory


def git_context(root: Path) -> dict:
    """Represent branch state without failing on an unborn or detached HEAD."""
    branch = _git(root, "symbolic-ref", "--quiet", "HEAD", optional=True)
    head = _git(root, "rev-parse", "--verify", "HEAD", optional=True)
    if not branch:
        branch = b"detached:" + head if head else b"unborn"
    return {"head": head, "branch": branch}


@contextmanager
def git_index_lock(root: Path):
    """Own Git's index lock for one short publication window."""
    index = Path(os.fsdecode(_git(root, "rev-parse", "--git-path", "index")))
    if not index.is_absolute():
        index = root / index
    lock = Path(str(index) + ".lock")
    token = _canonical({"owner": "vibe-state-exchange", "pid": os.getpid(), "nonce": uuid.uuid4().hex})
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise StateError(
            "git_busy",
            f"Another Git operation holds {lock}. Vibe never deletes a lock it does not own; "
            "confirm no Git or Vibe writer is active, then investigate the lock manually.",
        ) from error
    except OSError as error:
        raise StateError("git_context_error", f"Cannot take the Git index lock: {error}") from error
    with os.fdopen(descriptor, "wb") as stream:
        identity = os.fstat(stream.fileno())
        stream.write(token)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        yield lock
    finally:
        try:
            current = lock.lstat()
            if (stat.S_ISREG(current.st_mode)
                    and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino)
                    and lock.read_bytes() == token):
                lock.unlink()
        except OSError:
            pass


def directory(root: Path) -> Path:
    return root / EXCHANGE_RELATIVE


def _objects(root: Path) -> Path:
    return directory(root) / "objects"


def _read_bounded(path: Path, maximum: int) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise StateError("snapshot_incomplete", f"Missing or unsafe snapshot file: {path}")
        with path.open("rb") as stream:
            content = stream.read(maximum + 1)
    except OSError as error:
        raise StateError("snapshot_incomplete", f"Cannot read {path}: {error}") from error
    if len(content) > maximum:
        raise StateError("snapshot_incomplete", f"Oversized snapshot file: {path}")
    return content


def _write_exclusive(path: Path, content: bytes) -> None:
    """Create an immutable object without ever exposing a partial file.

    The bytes go to a sibling temporary file that is fsynced first and then
    linked into place. ``os.link`` is atomic and refuses to replace an existing
    name, so the exclusive-create guarantee survives while a reader can only
    ever observe either no object or the complete object. A kill during the
    write leaves a temporary file at worst, never a truncated object that a
    later export would report as ``snapshot_conflict``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}{TEMP_SUFFIX}{uuid.uuid4().hex}")
    try:
        with temporary.open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            existing = _read_bounded(path, MAX_OBJECT_BYTES)
            if existing != content:
                raise StateError("snapshot_conflict", f"Immutable object exists with different content: {path}")
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _ensure_object_ignore(root: Path) -> None:
    """Keep a killed publish's temporary file out of the repository index.

    A SIGKILL cannot run the ``finally`` that removes the temporary file, so the
    exchange directory carries an ignore rule for it. Without one, ``git add -A``
    in a user project would stage the orphan.
    """
    directory(root).mkdir(parents=True, exist_ok=True)
    ignore = directory(root) / ".gitignore"
    if not ignore.exists():
        ignore.write_text(f"*{TEMP_SUFFIX}*\n", encoding="utf-8")


def _decode(content: bytes, label: str) -> dict:
    try:
        value = json.loads(content)
    except (ValueError, UnicodeError) as error:
        raise StateError("snapshot_incomplete", f"Invalid JSON in {label}") from error
    if type(value) is not dict:
        raise StateError("snapshot_incomplete", f"Expected a JSON object in {label}")
    return value


def read_pointer(root: Path) -> dict | None:
    path = directory(root) / SNAPSHOT_NAME
    if not path.exists() and not path.is_symlink():
        return None
    pointer = _decode(_read_bounded(path, 4096), str(path))
    if set(pointer) != {"schema_version", "snapshot_id"}:
        raise StateError("snapshot_incomplete", "Malformed snapshot pointer")
    if type(pointer["schema_version"]) is not int or pointer["schema_version"] != SCHEMA_VERSION:
        raise StateError("snapshot_incomplete", "Unsupported snapshot pointer version")
    snapshot_id = pointer["snapshot_id"]
    if type(snapshot_id) is not str or len(snapshot_id) != 64:
        raise StateError("snapshot_incomplete", "Malformed snapshot identity")
    return pointer


def read_manifest(root: Path, snapshot_id: str) -> dict:
    if type(snapshot_id) is not str or len(snapshot_id) != 64:
        raise StateError("snapshot_incomplete", "Malformed snapshot identity")
    path = _objects(root) / f"{snapshot_id}.manifest.json"
    manifest = _decode(_read_bounded(path, 8192), str(path))
    if set(manifest) != MANIFEST_FIELDS:
        raise StateError("snapshot_incomplete", "Manifest has missing or unknown fields")
    content = {key: value for key, value in manifest.items() if key != "snapshot_id"}
    if manifest["snapshot_id"] != snapshot_id or _fingerprint(content) != snapshot_id:
        raise StateError("snapshot_incomplete", "Manifest digest does not match its identity")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA_VERSION:
        raise StateError("snapshot_incomplete", "Unsupported manifest version")
    if type(manifest["data_sha256"]) is not str or len(manifest["data_sha256"]) != 64:
        raise StateError("snapshot_incomplete", "Manifest payload digest is malformed")
    if manifest["parent_id"] is not None and (
            type(manifest["parent_id"]) is not str or len(manifest["parent_id"]) != 64):
        raise StateError("snapshot_incomplete", "Manifest parent identity is malformed")
    if type(manifest["exported_local_revision"]) is not int or manifest["exported_local_revision"] < 0:
        raise StateError("snapshot_incomplete", "Manifest revision is malformed")
    return manifest


def read_payload(root: Path, manifest: dict) -> dict:
    path = _objects(root) / f"{manifest['data_sha256']}.payload.json"
    content = _read_bounded(path, MAX_OBJECT_BYTES)
    if _digest_bytes(_normalized(content)) != manifest["data_sha256"]:
        raise StateError("snapshot_incomplete", "Snapshot payload digest does not match the manifest")
    return _decode(content, str(path))


def _descends_from(root: Path, manifest: dict, base_snapshot: str | None) -> bool:
    seen = set()
    current = manifest
    while True:
        identity = current["snapshot_id"]
        if identity == base_snapshot:
            return True
        parent = current["parent_id"]
        if parent is None:
            return base_snapshot is None
        if parent in seen:
            raise StateError("snapshot_conflict", "Snapshot history contains a cycle")
        seen.add(parent)
        current = read_manifest(root, parent)


def publish(store: Store, root: Path) -> dict:
    """Prepare the snapshot, then briefly own Git's index lock to publish it."""
    _require_repository(root)
    _ensure_object_ignore(root)
    before = git_context(root)
    bundle = store.export_bundle()
    payload = _canonical(bundle)
    data_sha256 = _digest_bytes(payload)
    pointer = read_pointer(root)
    parent_id = pointer["snapshot_id"] if pointer else None
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "project_id": store.project_id,
        "parent_id": parent_id,
        "branch": os.fsdecode(before["branch"]),
        "data_sha256": data_sha256,
        "exported_local_revision": bundle["local_revision"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    snapshot_id = _fingerprint(manifest)
    manifest["snapshot_id"] = snapshot_id
    _write_exclusive(_objects(root) / f"{data_sha256}.payload.json", payload)
    _write_exclusive(_objects(root) / f"{snapshot_id}.manifest.json", _canonical(manifest))
    store.begin_export(snapshot_id, bundle["local_revision"])
    try:
        with git_index_lock(root):
            if git_context(root) != before:
                raise StateError("git_context_drift", "Branch or HEAD changed during export preparation")
            if store.export_bundle()["local_revision"] != bundle["local_revision"]:
                raise StateError("stale_revision", "Local state changed during export preparation")
            path = directory(root) / SNAPSHOT_NAME
            path.parent.mkdir(parents=True, exist_ok=True)
            # Same temporary naming as the object writes, so the exchange
            # .gitignore also covers a pointer write killed mid-flight.
            temporary = path.with_name(f".{path.name}{TEMP_SUFFIX}{uuid.uuid4().hex}")
            try:
                with temporary.open("xb") as stream:
                    stream.write(_canonical({"schema_version": SCHEMA_VERSION, "snapshot_id": snapshot_id}))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
    except Exception:
        try:
            store.abandon_export("export aborted before the pointer was acknowledged")
        except StateError:
            pass
        raise
    exchange = store.finish_export(snapshot_id)
    return {
        "status": "exported", "snapshot_id": snapshot_id, "parent_id": parent_id,
        "data_sha256": data_sha256, "exported_local_revision": exchange["exported_local_revision"],
    }


def import_snapshot(store: Store, root: Path) -> dict:
    """Verify an incoming snapshot, then replace entity state and append new commands."""
    _require_repository(root)
    with git_index_lock(root):
        before = git_context(root)
        pointer = read_pointer(root)
        if pointer is None:
            raise StateError("snapshot_missing", "No published snapshot is present in this worktree")
        manifest = read_manifest(root, pointer["snapshot_id"])
        if manifest["project_id"] != store.project_id:
            raise StateError("foreign_snapshot", "Snapshot belongs to another project identity")
        exchange = store.exchange_state()
        if not _descends_from(root, manifest, exchange["base_snapshot"]):
            raise StateError("snapshot_diverged", "Snapshot does not descend from the recorded common base")
        if git_context(root) != before:
            raise StateError("git_context_drift", "Branch or HEAD changed during import")
        if store.status()["local_revision"] != exchange["exported_local_revision"]:
            raise StateError(
                "unexported_changes",
                "Local commands are not published; preserve both versions instead of overwriting them",
            )
        payload = read_payload(root, manifest)
        result = store.apply_import(payload, manifest["snapshot_id"])
    return {**result, "views_stale": True, "projection": "pending"}


def status(store: Store, root: Path) -> dict:
    """Read-only exchange bookkeeping; safe to call on a legacy or broken project."""
    exchange = store.exchange_state()
    local_revision = store.status()["local_revision"]
    pointer = read_pointer(root)
    return {
        "snapshot_id": pointer["snapshot_id"] if pointer else None,
        "base_snapshot": exchange["base_snapshot"],
        "exported_local_revision": exchange["exported_local_revision"],
        "local_revision": local_revision,
        "unexported_commands": local_revision - exchange["exported_local_revision"],
        "pending_kind": exchange["pending_kind"],
        "pending_snapshot": exchange["pending_snapshot"],
    }


def acknowledge_export(store: Store, root: Path) -> dict:
    """Operator recovery: confirm a pending export really is the published pointer."""
    _require_repository(root)
    exchange = store.exchange_state()
    if exchange["pending_kind"] != "export":
        raise StateError("exchange_conflict", "No pending export to acknowledge")
    with git_index_lock(root):
        pointer = read_pointer(root)
        if pointer is None or pointer["snapshot_id"] != exchange["pending_snapshot"]:
            raise StateError(
                "exchange_conflict",
                "The published pointer does not match the pending export; investigate the worktree "
                "before abandoning it",
            )
        result = store.finish_export(exchange["pending_snapshot"])
    return {
        "status": "acknowledged", "snapshot_id": result["base_snapshot"],
        "exported_local_revision": result["exported_local_revision"],
    }
