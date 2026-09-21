from __future__ import annotations

from contextlib import contextmanager
import hashlib
import html
import json
import os
from pathlib import Path
import stat
import uuid

from state_store import SCHEMA_VERSION, StateError, Store, native_path


_VIEW_NAMES = ("current-session.md", "progress.md", "handoff.md")
_MAX_FILE_BYTES = 2097152


def _encoded(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _display(value) -> str:
    text = html.escape(str(value)).replace("\n", " / ").replace("\t", " ")
    for character in ("\\", "`", "*", "_", "[", "]", "#", "|"):
        text = text.replace(character, "\\" + character)
    return text


def _header(title: str, snapshot: dict) -> list[str]:
    return [
        f"# {title}", "", "Generated read-only summary; user-authored notes belong outside this directory.", "",
        f"Project: {_display(snapshot['project_id'])}",
        f"Context: {_display(snapshot['context_id'])}", f"Revision: {snapshot['revision']}", "",
    ]


def _task_lines(task: dict) -> list[str]:
    lines = [f"- {_display(task['id'])}: {_display(task['title'])} ({task['status']})"]
    if task["goal_id"] is not None:
        lines.append(f"  Goal: {_display(task['goal_id'])}")
    if task["next_action"]:
        lines.append(f"  Next action: {_display(task['next_action'])}")
    if task["summary"]:
        lines.append(f"  Implementation summary (not verification): {_display(task['summary'])}")
    if task["cancel_reason"]:
        lines.append(f"  Cancellation: {_display(task['cancel_reason'])}")
    blocker = task["blocker"]
    if blocker:
        lines.extend([
            f"  Waiting on {blocker['kind']}: {_display(blocker['reason'])}",
            f"  Resume when: {_display(blocker['resume_when'])}",
        ])
        if blocker["question_ref"]:
            lines.append(f"  Question: {_display(blocker['question_ref'])}")
    return lines


def _render(snapshot: dict) -> dict[str, bytes]:
    session = _header("Current session", snapshot)
    active = snapshot["current_task"]
    session.extend(["## Active run", ""])
    if active:
        session.append(f"Run: {_display(snapshot['current_run']['id'])}")
        session.extend(_task_lines(active))
    else:
        session.append("No active run. Waiting and handed-off tasks do not occupy the active slot.")
    session.extend(["", "## Recently updated tasks (bounded)", ""])
    for task in snapshot["tasks"]:
        session.extend(_task_lines(task))
    progress = _header("Progress", snapshot)
    progress.extend(["## Recent accepted commands (newest first, bounded)", ""])
    for entry in snapshot["history"]:
        receipt = entry["receipt"]
        result = receipt["result"]
        entity = result.get("task_id", result.get("goal_id"))
        progress.append(
            f"- Local {entry['local_sequence']} (origin {_display(receipt['context_id'])}"
            f"@{receipt['revision']}): {_display(receipt['action'])} / {_display(entity)} / "
            f"{_display(result['status'])}; command {_display(receipt['command_id'])}"
        )
    if not snapshot["history"]:
        progress.append("No commands accepted yet.")
    handoff = _header("Handoff", snapshot)
    handoff.extend(["Completion requires future evidence gates; implemented-unverified is not done.", ""])
    if active:
        handoff.extend(["## Active task", "", *_task_lines(active), ""])
    handoff.extend(["## Recent task context (bounded; not a complete backlog)", ""])
    for task in snapshot["tasks"]:
        handoff.extend(_task_lines(task))
    return {
        name: ("\n".join(lines) + "\n").encode("utf-8")
        for name, lines in zip(_VIEW_NAMES, (session, progress, handoff))
    }


def _read(path: Path, maximum: int = _MAX_FILE_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise StateError("projection_incomplete", f"Missing or unsafe generated file: {path}")
    with path.open("rb") as stream:
        content = stream.read(maximum + 1)
    if len(content) > maximum:
        raise StateError("projection_incomplete", f"Oversized generated file: {path}")
    return content


def _decode(content: bytes, path: Path) -> dict:
    try:
        value = json.loads(content)
    except (ValueError, UnicodeError) as error:
        raise StateError("projection_incomplete", f"Invalid generated JSON: {path}") from error
    if type(value) is not dict:
        raise StateError("projection_incomplete", f"Expected generated JSON object: {path}")
    return value


def _directory(path: Path) -> None:
    if path.is_symlink():
        raise StateError("projection_conflict", f"Refusing symlinked projection directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def _write(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


@contextmanager
def _publisher_lock(destination: Path, store: Store):
    path = destination / ".publish.lock"
    token = uuid.uuid4().hex
    content = _encoded({"token": token, "project_id": store.project_id, "context_id": store.context_id})
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise StateError("projection_busy", f"Publisher lock exists: {path}; explicit ownership recovery required") from error
    with os.fdopen(descriptor, "wb") as stream:
        identity = os.fstat(stream.fileno())
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        yield token
    finally:
        try:
            current = path.lstat()
            same_file = (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino)
            if stat.S_ISREG(current.st_mode) and same_file and _read(path, 4096) == content:
                path.unlink()
        except (OSError, StateError):
            pass


def _inspect_pointer(destination: Path, store: Store) -> dict | None:
    """Read CURRENT.json, tolerating a generation that only needs rebuilding.

    Generated content is deterministic for a revision, so a missing generation,
    manifest or view file is reported for in-place repair by the publisher rather
    than treated as fatal. Bytes that exist but disagree still fail closed.
    """
    path = destination / "CURRENT.json"
    if not path.exists() and not path.is_symlink():
        return None
    pointer = _decode(_read(path, 8192), path)
    fields = {"schema_version", "project_id", "context_id", "revision", "generation", "manifest_sha256"}
    if (set(pointer) != fields or type(pointer["schema_version"]) is not int
            or pointer["schema_version"] != SCHEMA_VERSION or type(pointer["revision"]) is not int
            or pointer["revision"] < 0 or pointer["generation"] != f"views/{pointer['revision']}"):
        raise StateError("projection_incomplete", "Malformed CURRENT.json pointer")
    if pointer["project_id"] != store.project_id or pointer["context_id"] != store.context_id:
        raise StateError("context_mismatch", "View destination belongs to another project/context")
    generation = destination / pointer["generation"]
    if generation.is_symlink():
        raise StateError("projection_conflict", "CURRENT.json references an unsafe generation")
    if not generation.is_dir():
        return pointer
    manifest_path = generation / "manifest.json"
    if manifest_path.is_symlink() or (manifest_path.exists() and not manifest_path.is_file()):
        raise StateError("projection_conflict", "CURRENT.json references an unsafe generation manifest")
    if not manifest_path.exists():
        return pointer
    content = _read(manifest_path, 8192)
    manifest = _decode(content, manifest_path)
    if _digest(content) != pointer["manifest_sha256"]:
        raise StateError("projection_incomplete", "Manifest hash does not match CURRENT.json")
    expected = {key: pointer[key] for key in ("schema_version", "project_id", "context_id", "revision")}
    expected["files"] = {}
    for name in _VIEW_NAMES:
        target = generation / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise StateError("projection_conflict", f"Unsafe generated file: {target}")
        if not target.exists():
            return pointer
        expected["files"][name] = _digest(_read(target))
    if _encoded(manifest) != _encoded(expected):
        raise StateError("projection_incomplete", "Generation manifest or file hashes do not match")
    return pointer


def publish(store: Store, destination: Path) -> dict:
    """Publish immutable views; a failure never rolls back a committed command.

    Cooperating publishers serialize before acquiring their read snapshot. A crash
    leaves the owned lock for explicit recovery, rather than guessing lock age.
    """
    destination = native_path(destination)
    try:
        _directory(destination)
        with _publisher_lock(destination, store) as token:
            views = destination / "views"
            _directory(views)
            previous = _inspect_pointer(destination, store)
            snapshot = store.view_snapshot()
            revision = snapshot["revision"]
            if previous and previous["revision"] > revision:
                raise StateError("projection_conflict", "Refusing to move CURRENT.json backwards")
            contents = _render(snapshot)
            manifest = {
                "schema_version": SCHEMA_VERSION, "project_id": snapshot["project_id"],
                "context_id": snapshot["context_id"], "revision": revision,
                "files": {name: _digest(content) for name, content in contents.items()},
            }
            manifest_bytes = _encoded(manifest)
            if (previous and previous["revision"] == revision
                    and previous["manifest_sha256"] != _digest(manifest_bytes)):
                raise StateError("projection_conflict", "Generated content for this revision changed")
            contents["manifest.json"] = manifest_bytes
            generation = views / str(revision)
            repaired: list[str] = []
            if generation.exists() or generation.is_symlink():
                if generation.is_symlink() or not generation.is_dir():
                    raise StateError("projection_conflict", f"Unsafe generation path: {generation}")
                for name, content in contents.items():
                    target = generation / name
                    if target.is_symlink() or (target.exists() and not target.is_file()):
                        raise StateError("projection_conflict", f"Unsafe generated file: {target}")
                    if not target.exists():
                        _write(target, content)
                        repaired.append(name)
                        continue
                    if _read(target) != content:
                        raise StateError("projection_conflict", f"Immutable generation differs: {target}")
                if repaired:
                    _sync_directory(generation)
            else:
                staging = views / f".{revision}-{token}.tmp"
                staging.mkdir()
                for name, content in contents.items():
                    _write(staging / name, content)
                _sync_directory(staging)
                staging.rename(generation)
                _sync_directory(views)
            pointer = {
                "schema_version": SCHEMA_VERSION, "project_id": snapshot["project_id"],
                "context_id": snapshot["context_id"], "revision": revision,
                "generation": f"views/{revision}", "manifest_sha256": _digest(manifest_bytes),
            }
            if previous != pointer:
                temporary_pointer = destination / f".CURRENT-{token}.tmp"
                _write(temporary_pointer, _encoded(pointer))
                os.replace(temporary_pointer, destination / "CURRENT.json")
                _sync_directory(destination)
            acknowledged = store.projection_done(revision)
            return {**pointer, "projection_pending": not acknowledged,
                    "repaired": sorted(repaired), "destination": str(destination)}
    except OSError as error:
        raise StateError("projection_failed", f"View publication failed at {destination}: {error}") from error
