"""Agent-owned semantic project memory (the two long Markdown notes)."""
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

FILES = {"current_session": "current-session.md", "progress": "progress.md"}
MAX_NOTE_CHARS = 100_000
TEMP_SUFFIX = ".memory-tmp-"


def _log_dir(root: Path) -> Path:
    root = Path(root).resolve()
    log = root / ".project-log"
    if log.is_symlink():
        raise ValueError(".project-log must not be a symlink")
    if not log.is_dir():
        raise ValueError("initialized .project-log directory required")
    return log


def _target(log: Path, key: str) -> Path:
    target = log / FILES[key]
    if target.is_symlink():
        raise ValueError(f"refusing to write through a symlink: {FILES[key]}")
    return target


def _validate(key: str, content: object) -> str:
    if not isinstance(content, str):
        raise ValueError(f"{key} must be a string")
    if not content.strip():
        raise ValueError(f"{key} must not be empty")
    if len(content) > MAX_NOTE_CHARS:
        raise ValueError(f"{key} exceeds {MAX_NOTE_CHARS} characters")
    return content.replace("\r\n", "\n")


def _replace(target: Path, text: str) -> None:
    try:
        mode = target.stat().st_mode & 0o777
    except FileNotFoundError:
        mode = 0o664
    temporary = target.with_name(f"{target.name}{TEMP_SUFFIX}{uuid.uuid4().hex}")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def read_memory(root: Path) -> dict:
    log = _log_dir(root)
    notes: dict = {}
    for key, name in FILES.items():
        target = _target(log, key)
        if target.is_file():
            text = target.read_text(encoding="utf-8")
            notes[key] = text
            notes[f"{key}_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
        else:
            notes[key] = ""
            notes[f"{key}_sha256"] = None
    return notes


def sync_memory(root: Path, payload: object) -> dict:
    if not isinstance(payload, dict) or not payload:
        raise ValueError("expected current_session and/or progress keys")
    unknown = sorted(set(payload) - set(FILES))
    if unknown:
        raise ValueError(f"unsupported memory keys: {unknown}")
    log = _log_dir(root)
    prepared = [(_key, _target(log, _key), _validate(_key, payload[_key]))
                for _key in FILES if _key in payload]
    updated = []
    for key, target, text in prepared:
        _replace(target, text)
        updated.append(FILES[key])
    return {
        "updated": updated,
        "atomicity": "per-file",
        "note": "Each note is replaced atomically; the pair is not a single transaction.",
    }
