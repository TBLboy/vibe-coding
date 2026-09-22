from __future__ import annotations

import hashlib
import json
from pathlib import Path

STATE_FILE = ".vibe-workflow-state.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_state(target: Path) -> dict:
    path = target / STATE_FILE
    if not path.exists():
        return {"version": None, "managed_hashes": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": None, "managed_hashes": {}}


def save_state(target: Path, version: str, hashes: dict[str, str]) -> None:
    payload = {"version": version, "managed_hashes": hashes}
    (target / STATE_FILE).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
