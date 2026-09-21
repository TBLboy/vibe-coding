"""Dependency-aware evidence invalidation and a conservative completion gate.

Invalidation is driven by a reverse index over the exact inputs an evidence
record covers, not by path-prefix intersection. A changed path only reaches
evidence that actually covers it, and `json-field` evidence is re-read so an
unrelated edit in the same file does not invalidate it.

The completion gate re-fingerprints the covered inputs at decision time, so a
manual edit, a shell write or a `git checkout` is detected no matter how it
reached the worktree.
"""
from __future__ import annotations

import os
from pathlib import Path

from state_evidence import fingerprint_file, selector_problem
from state_store import StateError


MAX_RECORDS = 20000
MAX_CHANGED = 4096
REVIEW_KIND = "review"


def _records(value) -> list[dict]:
    if type(value) is not list or len(value) > MAX_RECORDS:
        raise StateError("invalid_input", "records must be a bounded list")
    for entry in value:
        if type(entry) is not dict or type(entry.get("id")) is not str or type(entry.get("selectors")) is not list:
            raise StateError("invalid_input", "each record needs an id and a selector list")
    return value


def _key(path: str, base: Path) -> str:
    """Stable comparison key: root-relative POSIX when inside the root, else absolute."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = os.path.normcase(os.path.abspath(os.fspath(candidate)))
    root_key = os.path.normcase(os.path.abspath(os.fspath(base)))
    if resolved == root_key:
        return "."
    prefix = root_key.rstrip(os.sep) + os.sep
    if resolved.startswith(prefix):
        return resolved[len(prefix):].replace("\\", "/")
    return resolved.replace("\\", "/")


def _identity(value) -> str | None:
    """Comparable actor identity: trimmed and case-insensitive, or None when unnamed."""
    if type(value) is not str:
        return None
    normalized = value.strip().casefold()
    return normalized or None


def _covered(entry, base: Path) -> set[str]:
    keys = set()
    for selector in entry["selectors"]:
        if type(selector) is dict and type(selector.get("path")) is str and selector["path"].strip():
            keys.add(_key(selector["path"], base))
    return keys


def build_index(records, root=None) -> dict:
    """Reverse index from covered input to the evidence that covers it."""
    base = Path(root).resolve() if root is not None else Path.cwd().resolve()
    index: dict[str, list[dict]] = {}
    for entry in _records(records):
        for selector in entry["selectors"]:
            if selector_problem(selector) is not None:
                continue
            key = _key(selector["path"], base)
            index.setdefault(key, []).append(
                {"evidence_id": entry["id"], "selector": selector["selector"],
                 "field": selector.get("field"), "digest": selector.get("digest")}
            )
    return {key: sorted(value, key=lambda item: (item["evidence_id"], item["selector"]))
            for key, value in sorted(index.items())}


def invalidate(records, changed_paths, root) -> dict:
    """Decide which evidence a set of changed paths actually affects.

    A record whose covered input changed is stale; a record that depends on stale
    evidence becomes stale too, so a downstream claim is never left looking current.
    """
    if type(changed_paths) is not list or len(changed_paths) > MAX_CHANGED:
        raise StateError("invalid_input", "changed_paths must be a bounded list")
    base = Path(root).resolve()
    changed = []
    for path in changed_paths:
        if type(path) is not str or not path.strip():
            raise StateError("invalid_input", "changed paths must be non-empty strings")
        changed.append(_key(path, base))
    entries = _records(records)
    reasons_by_id: dict[str, list[str]] = {}
    for entry in entries:
        reasons: list[str] = []
        for selector in entry["selectors"]:
            problem = selector_problem(selector)
            if problem is not None:
                # A selector that cannot be evaluated cannot be shown to be
                # unaffected, so the record is reported rather than left current.
                reasons.append(f"selector cannot be evaluated: {problem}")
                continue
            if _key(selector["path"], base) not in changed:
                continue
            recorded = selector.get("digest")
            if recorded is None:
                reasons.append(f"{selector['path']} changed and no digest was recorded")
                continue
            if selector["selector"] == "json-field":
                target = Path(selector["path"])
                if not target.is_absolute():
                    target = base / target
                try:
                    current = fingerprint_file(target, selector["selector"], selector.get("field"))
                except StateError as error:
                    reasons.append(f"{selector['path']} could not be re-read: {error.code}")
                    continue
                if current["digest"] != recorded:
                    reasons.append(f"covered field {selector.get('field')!r} of {selector['path']} changed")
                continue
            reasons.append(f"covered input {selector['path']} changed")
        if reasons:
            reasons_by_id[entry["id"]] = reasons
    dependents: dict[str, list[str]] = {}
    for entry in entries:
        dependencies = entry.get("depends_on") or []
        if type(dependencies) is not list:
            dependencies = []
        for dependency in dependencies:
            if type(dependency) is str:
                dependents.setdefault(dependency, []).append(entry["id"])
    stale = set(reasons_by_id)
    for _ in range(len(entries) + 1):
        added = False
        for dependency, consumers in dependents.items():
            if dependency not in stale:
                continue
            for consumer in consumers:
                if consumer in reasons_by_id:
                    continue
                reasons_by_id[consumer] = [f"depends on stale evidence {dependency}"]
                stale.add(consumer)
                added = True
        if not added:
            break
    affected = {identifier: {"status": "stale", "reasons": reasons}
                for identifier, reasons in reasons_by_id.items()}
    untouched = [entry["id"] for entry in entries if entry["id"] not in affected]
    return {
        "changed_paths": changed,
        "affected": affected,
        "untouched": sorted(untouched),
        "stale_count": len(affected),
        "untouched_count": len(untouched),
    }


def check(records, root) -> dict:
    """Report dependency, selector and applicability problems conservatively."""
    from state_evidence import applicability

    entries = _records(records)
    known = {entry["id"] for entry in entries}
    problems: list[dict] = []
    for entry in entries:
        dependencies = entry.get("depends_on") or []
        if type(dependencies) is not list or any(type(item) is not str for item in dependencies):
            problems.append({"evidence_id": entry["id"], "kind": "invalid_dependency",
                             "detail": "depends_on must be a list of evidence ids"})
            dependencies = []
        for dependency in dependencies:
            if dependency not in known:
                problems.append({"evidence_id": entry["id"], "kind": "missing_dependency",
                                 "detail": f"depends on unknown evidence {dependency}"})
        if entry["id"] in dependencies:
            problems.append({"evidence_id": entry["id"], "kind": "cycle",
                             "detail": "evidence depends on itself"})
        for selector in entry["selectors"]:
            problem = selector_problem(selector)
            if problem is not None:
                problems.append({"evidence_id": entry["id"], "kind": "selector_mismatch",
                                 "detail": problem})
    for entry in entries:
        verdict = applicability(entry, root)
        for detail in verdict["selectors"]:
            if detail["status"] in {"missing_input", "selector_mismatch", "binary_input"}:
                problems.append({"evidence_id": entry["id"], "kind": detail["status"],
                                 "detail": detail.get("reason", detail["path"])})
    return {
        "checked": len(entries),
        "problems": problems,
        "blocking": [problem for problem in problems
                     if problem["kind"] in {"missing_dependency", "cycle", "selector_mismatch",
                                            "missing_input", "invalid_dependency", "binary_input"}],
    }


def gate(records, root, task_id: str | None = None, before=None, risk_class: str | None = None) -> dict:
    """Completion decision for one task's evidence; never silently passes."""
    from state_evidence import applicability

    if risk_class not in {None, "quick", "standard", "strict"}:
        raise StateError("invalid_input", f"unknown risk class: {risk_class!r}")
    entries = [entry for entry in _records(records)
               if task_id is None or task_id in (entry.get("tasks") or [])]
    blocking: list[dict] = []
    fallback = False
    if not entries:
        blocking.append({"kind": "no_evidence", "detail": "no evidence covers this task"})
    if before is not None:
        if type(before) is not dict:
            raise StateError("invalid_input", "before must be a mapping of path to digest")
        for path, recorded in before.items():
            target = Path(path)
            if not target.is_absolute():
                target = Path(root) / path
            try:
                current = fingerprint_file(target, "raw-file")["digest"]
            except StateError as error:
                blocking.append({"kind": "changed_during_verification", "path": path, "detail": error.code})
                continue
            if current != recorded:
                blocking.append({"kind": "changed_during_verification", "path": path,
                                 "detail": "input changed after it was fingerprinted"})
    for entry in entries:
        if entry.get("result") not in {"passed"}:
            blocking.append({"evidence_id": entry["id"], "kind": "result_not_passed",
                             "detail": f"recorded result is {entry.get('result')!r}"})
        verdict = applicability(entry, root)
        if verdict["applicability"] != "current":
            blocking.append({"evidence_id": entry["id"], "kind": "not_applicable",
                             "detail": verdict["applicability"]})
    if risk_class == "strict":
        if task_id is None:
            blocking.append({
                "kind": "task_identity_required",
                "detail": "a strict completion decision must name the task so the review can be bound to it",
            })
        else:
            base = Path(root)
            accepted = {key for entry in entries if entry.get("kind") != REVIEW_KIND
                        for key in _covered(entry, base)}
            reviews = [entry for entry in entries
                       if entry.get("kind") == REVIEW_KIND and entry.get("result") == "passed"
                       and applicability(entry, root)["applicability"] == "current"]
            if not reviews:
                blocking.append({
                    "kind": "missing_independent_review",
                    "detail": "a strict task needs a passed review record whose covered inputs are still current",
                })
            else:
                covering = [entry for entry in reviews if accepted <= _covered(entry, base)]
                if not covering:
                    uncovered = sorted(accepted - {key for entry in reviews for key in _covered(entry, base)})
                    blocking.append({
                        "kind": "review_does_not_cover_artifacts",
                        "detail": "no current review covers every accepted artifact; uncovered: "
                                  + (", ".join(uncovered) if uncovered else "none"),
                    })
                else:
                    authors = {_identity(entry.get("author")) for entry in entries if _identity(entry.get("author"))}
                    independent = [entry for entry in covering
                                   if _identity(entry.get("reviewer"))
                                   and authors and _identity(entry.get("reviewer")) not in authors]
                    if independent:
                        pass
                    elif any(entry.get("serial_role_fallback") for entry in covering):
                        fallback = True
                    else:
                        blocking.append({
                            "kind": "review_not_independent",
                            "detail": "review record names the same author as the implementation, or names no reviewer",
                        })
    decision = "blocked" if blocking else ("allowed-with-fallback" if fallback else "allowed")
    return {
        "task_id": task_id,
        "risk_class": risk_class,
        "evidence_checked": len(entries),
        "decision": decision,
        "blocking": blocking,
        "independent_review": "not-required" if risk_class != "strict"
                              else ("fallback" if fallback else ("verified" if not blocking else "missing")),
        "note": "a recorded pass never endorses a changed input",
    }
