"""Agent-owned semantic project memory (the two long Markdown notes).

The structured facts live in the transactional store and the Git ledger. These
two notes carry meaning the Agent decides: the active session scene and the
stage-level progress summary. No prose is synthesized here -- the caller
supplies the text, this module only validates it and replaces each file
crash-safely.

Two honesty constraints are deliberate:

* The replacement is atomic **per file**, not across both. A sync that updates
  both notes can leave them one revision apart if the process dies in between.
  Callers must treat the two notes as independently durable; ``vibe memory read``
  reports a per-file digest so a caller can tell which one landed.
* Types, non-emptiness and size are validated; whether the prose actually agrees
  with Task/Record facts is not. The Agent must check that against
  ``vibe status`` and ``vibe record show`` before syncing.
"""
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
    """Replace one note atomically, keeping its existing permission bits."""
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
    """Return both notes plus a digest, so a caller can detect a partial sync."""
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
    """Replace one or both notes. Omitted keys are left untouched."""
    if not isinstance(payload, dict) or not payload:
        raise ValueError("expected current_session and/or progress keys")
    unknown = sorted(set(payload) - set(FILES))
    if unknown:
        raise ValueError(f"unsupported memory keys: {unknown}")

    log = _log_dir(root)
    # Validate everything, and resolve every target, before writing anything, so
    # a rejected payload cannot leave one of the two notes updated.
    prepared = [(key, _target(log, key), _validate(key, payload[key])) for key in FILES if key in payload]

    updated = []
    for key, target, text in prepared:
        _replace(target, text)
        updated.append(FILES[key])
    return {
        "updated": updated,
        "atomicity": "per-file",
        "note": "Each note is replaced atomically; the pair is not a single transaction.",
    }
