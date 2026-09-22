"""Versioned evidence: a historical result separated from current applicability.

`result` records what happened when the check ran. `applicability` records
whether the covered inputs still match. A historical pass never endorses the
current files, and a changed file never rewrites history: it only makes the
evidence stale.

Selectors are explicit so that normalization is a deliberate choice:

- `raw-file` hashes the exact bytes, so whitespace, math symbols and binary
  differences are all visible.
- `text-lf` additionally normalizes CRLF to LF and refuses binary input instead
  of silently hashing a mangled copy.
- `json-field` hashes only the selected field, so unrelated edits do not
  invalidate a check that never covered them.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from state_store import StateError


SELECTORS = ("raw-file", "text-lf", "json-field")
RESULTS = ("passed", "failed", "partial", "unknown", "superseded", "invalid")
APPLICABILITY = ("current", "stale", "unknown")
LEGACY_RESULTS = {
    "valid": "passed",
    "failed": "failed",
    "candidate": "unknown",
    "stale": "unknown",
    "superseded": "superseded",
    "invalid": "invalid",
}
MAX_FILE_BYTES = 64 * 1024 * 1024


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read(path: Path) -> bytes:
    try:
        if path.is_symlink() or not path.is_file():
            raise StateError("missing_input", f"Not a regular file: {path}")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise StateError("oversized_input", f"Input exceeds {MAX_FILE_BYTES} bytes: {path}")
        return path.read_bytes()
    except FileNotFoundError as error:
        raise StateError("missing_input", f"Missing input: {path}") from error
    except OSError as error:
        raise StateError("unreadable_input", f"Cannot read {path}: {error}") from error


def _field(document, field: str):
    current = document
    for part in field.split("."):
        if isinstance(current, list):
            if not part.isdigit() or int(part) >= len(current):
                raise StateError("selector_mismatch", f"field {field!r} does not match the document")
            current = current[int(part)]
        elif isinstance(current, dict):
            if part not in current:
                raise StateError("selector_mismatch", f"field {field!r} does not match the document")
            current = current[part]
        else:
            raise StateError("selector_mismatch", f"field {field!r} does not match the document")
    return current


def selector_problem(selector) -> str | None:
    """Explain why a stored selector cannot be evaluated, or None when it can.

    Shared by `record` and `applicability` so an unevaluable selector can never be
    stored, and a hand-forged one is reported instead of raising an unhandled error.
    """
    if type(selector) is not dict:
        return "each evidence selector must be an object"
    if type(selector.get("path")) is not str or not selector["path"].strip():
        return "each evidence selector needs a non-empty path"
    if selector.get("selector") not in SELECTORS:
        return f"unknown selector: {selector.get('selector')!r}"
    if selector["selector"] == "json-field":
        if type(selector.get("field")) is not str or not selector["field"].strip():
            return "json-field requires a non-empty field"
    elif selector.get("field") is not None:
        return f"{selector['selector']} does not take a field"
    return None


def fingerprint_file(path, selector: str = "raw-file", field: str | None = None) -> dict:
    """Digest one input under an explicit selector."""
    if selector not in SELECTORS:
        raise StateError("invalid_input", f"unknown selector: {selector!r}")
    target = Path(path)
    content = _read(target)
    if selector == "raw-file":
        if field is not None:
            raise StateError("invalid_input", "raw-file does not take a field")
        payload = content
    elif selector == "text-lf":
        if field is not None:
            raise StateError("invalid_input", "text-lf does not take a field")
        if b"\x00" in content:
            raise StateError("binary_input", f"text-lf refuses binary input: {target}")
        payload = content.replace(b"\r\n", b"\n")
    else:
        if not field:
            raise StateError("invalid_input", "json-field requires a field")
        try:
            document = json.loads(content.decode("utf-8"))
        except (ValueError, UnicodeError) as error:
            raise StateError("selector_mismatch", f"json-field needs UTF-8 JSON: {target}") from error
        selected = _field(document, field)
        try:
            payload = json.dumps(
                selected, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except ValueError as error:
            raise StateError(
                "invalid_input",
                f"json-field {field!r} is not JSON compliant in {target}: {error}",
            ) from error
    result = {"selector": selector, "path": os.fspath(target), "digest": _digest(payload)}
    if field is not None:
        result["field"] = field
    return result


def record(
    evidence_id: str,
    kind: str,
    subject: str,
    result: str,
    selectors,
    command: str | None = None,
    result_ref: str | None = None,
    origin_revision: int | None = None,
    author: str | None = None,
    reviewer: str | None = None,
    serial_role_fallback: bool | None = None,
) -> dict:
    """Build one evidence record; result and applicability are separate fields."""
    for value, name in ((evidence_id, "evidence_id"), (kind, "kind"), (subject, "subject")):
        if type(value) is not str or not value.strip():
            raise StateError("invalid_input", f"{name} must be non-empty text")
    if result not in RESULTS:
        raise StateError("invalid_input", f"result must be one of {RESULTS}")
    if type(selectors) is not list or not selectors:
        raise StateError("invalid_input", "at least one selector is required")
    normalized = []
    for selector in selectors:
        if type(selector) is not dict or set(selector) - {"selector", "path", "digest", "field"}:
            raise StateError("invalid_input", "selector has unknown fields")
        problem = selector_problem(selector)
        if problem is not None:
            raise StateError("invalid_input", problem)
        digest = selector.get("digest")
        if digest is not None and (type(digest) is not str or len(digest) != 64):
            raise StateError("invalid_input", "selector digest must be a sha256 hex string or null")
        normalized.append({key: selector[key] for key in ("selector", "path", "digest", "field") if key in selector})
    if origin_revision is not None and (type(origin_revision) is not int or origin_revision < 0):
        raise StateError("invalid_input", "origin_revision must be a non-negative integer")
    for value, name in ((author, "author"), (reviewer, "reviewer")):
        if value is not None and (type(value) is not str or not value.strip()):
            raise StateError("invalid_input", f"{name} must be non-empty text or null")
    if serial_role_fallback is not None and type(serial_role_fallback) is not bool:
        raise StateError("invalid_input", "serial_role_fallback must be a boolean or null")
    return {
        "schema_version": 1,
        "id": evidence_id,
        "kind": kind,
        "subject": subject,
        "result": result,
        "selectors": normalized,
        "command": command,
        "result_ref": result_ref,
        "origin_revision": origin_revision,
        "author": author,
        "reviewer": reviewer,
        "serial_role_fallback": serial_role_fallback,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def applicability(evidence: dict, root) -> dict:
    """Compare recorded selectors with the current inputs; never rewrites history."""
    if type(evidence) is not dict or "selectors" not in evidence:
        raise StateError("invalid_input", "evidence record is required")
    if type(evidence["selectors"]) is not list:
        raise StateError("invalid_input", "evidence selectors must be a list")
    base = Path(root)
    details = []
    for selector in evidence["selectors"]:
        problem = selector_problem(selector)
        if problem is not None:
            details.append({
                "path": selector.get("path") if type(selector) is dict else None,
                "status": "invalid_input", "reason": problem,
            })
            continue
        target = Path(selector["path"])
        if not target.is_absolute():
            target = base / target
        recorded = selector.get("digest")
        if recorded is None:
            details.append({"path": selector["path"], "status": "unknown", "reason": "no digest was recorded"})
            continue
        try:
            current = fingerprint_file(target, selector["selector"], selector.get("field"))
        except StateError as error:
            details.append({"path": selector["path"], "status": error.code, "reason": str(error)})
            continue
        if current["digest"] == recorded:
            details.append({"path": selector["path"], "status": "match"})
        else:
            details.append({"path": selector["path"], "status": "changed", "current_digest": current["digest"]})
    stale_statuses = {"changed", "missing_input", "unreadable_input", "oversized_input",
                      "selector_mismatch", "binary_input"}
    if not details:
        overall = "unknown"
    elif any(detail["status"] in stale_statuses for detail in details):
        overall = "stale"
    elif any(detail["status"] != "match" for detail in details):
        # A selector that could not be evaluated - unknown, invalid or unrecognized -
        # never counts as current; only an all-match record is current.
        overall = "unknown"
    else:
        overall = "current"
    return {
        "evidence_id": evidence.get("id"),
        "result": evidence.get("result"),
        "applicability": overall,
        "selectors": details,
        "historical_result_preserved": True,
    }


def from_legacy(entry: dict, root=None) -> dict:
    """Convert one legacy evidence entry without discarding its original hashes."""
    if type(entry) is not dict:
        raise StateError("invalid_input", "legacy evidence entry must be an object")
    for key in ("id", "kind", "subject"):
        if type(entry.get(key)) is not str or not entry[key].strip():
            raise StateError("invalid_input", f"legacy entry needs {key}")
    legacy_status = entry.get("status")
    if legacy_status not in LEGACY_RESULTS:
        raise StateError("invalid_input", f"unknown legacy status: {legacy_status!r}")
    binding = entry.get("version_binding") or {}
    if type(binding) is not dict:
        raise StateError("invalid_input", "legacy version_binding must be an object")
    hashes = binding.get("file_hashes") or {}
    if type(hashes) is not dict:
        raise StateError("invalid_input", "legacy version_binding.file_hashes must be an object")
    covers = entry.get("covers") or {}
    if type(covers) is not dict:
        raise StateError("invalid_input", "legacy covers must be an object")
    files = covers.get("files") or []
    if type(files) is not list or any(type(path) is not str or not path.strip() for path in files):
        raise StateError("invalid_input", "legacy covers.files must be a list of non-empty paths")
    selectors = []
    for path in files:
        recorded = hashes.get(path)
        selectors.append({"selector": "raw-file", "path": path, "digest": recorded})
    if not selectors:
        selectors = [{"selector": "raw-file", "path": entry["id"], "digest": None}]
    converted = record(
        evidence_id=entry["id"],
        kind=entry["kind"],
        subject=entry["subject"],
        result=LEGACY_RESULTS[legacy_status],
        selectors=selectors,
        command=entry.get("command"),
        result_ref=entry.get("result_ref"),
    )
    converted["legacy_status"] = legacy_status
    converted["recorded_at"] = entry.get("recorded_at") or converted["recorded_at"]
    for key in ("tasks", "requirements"):
        values = covers.get(key) or []
        if type(values) is not list or any(type(item) is not str or not item.strip() for item in values):
            raise StateError("invalid_input", f"legacy covers.{key} must be a list of ids")
        if values:
            converted[key] = list(values)
    for key in ("git_commit", "diff_hash"):
        value = binding.get(key)
        if value is None:
            continue
        if type(value) is not str or not value.strip():
            raise StateError("invalid_input", f"legacy version_binding.{key} must be text or null")
        converted[key] = value
    if root is not None:
        converted["applicability"] = applicability(converted, root)["applicability"]
    return converted


def summarize(records) -> dict:
    """Count results and applicability independently."""
    if type(records) is not list:
        raise StateError("invalid_input", "records must be a list")
    results = {name: 0 for name in RESULTS}
    states = {name: 0 for name in APPLICABILITY}
    for entry in records:
        result = entry.get("result")
        if result in results:
            results[result] += 1
        state = entry.get("applicability")
        if isinstance(state, dict):
            state = state.get("applicability")
        if state in states:
            states[state] += 1
    return {"total": len(records), "results": results, "applicability": states}
