"""Deterministic task risk routing and bounded per-task context.

The policy is explicit rather than guessed from free text: the caller states
the change signals, the policy maps them to a class, and every class documents
its reasons, minimum verification, required records and escalation triggers.
An unknown or empty signal set is deliberately routed to `standard` rather than
assumed low risk.
"""
from __future__ import annotations

import json

from state_store import StateError, Store


CLASSES = ("quick", "standard", "strict")
HIGH_IMPACT = ("data", "conclusion", "public-interface", "security", "submission-format", "cross-module")
LOW_IMPACT = ("docs-only", "formatting-only", "comment-only")
ALL_SIGNALS = HIGH_IMPACT + LOW_IMPACT + ("config", "refactor", "test-only", "dependency-update")
MAX_SIGNALS = 32
MAX_QUICK_FILES = 1
MAX_STANDARD_FILES = 5
MAX_PATHS = 512
DEFAULT_CONTEXT_BUDGET = 4096
MIN_CONTEXT_BUDGET = 512
MAX_CONTEXT_BUDGET = 262144

POLICY = {
    "quick": {
        "reasons": [
            "every declared signal is low-impact and the change is reversible",
            "the change touches at most one file",
        ],
        "minimum_verification": [
            "re-read or re-render the changed artifact once and confirm the intended effect",
        ],
        "required_records": [
            "one compact task status update with the exact next action",
        ],
        "escalate_when": [
            "the change reaches a second file, a data/conclusion/interface/security/submission input, or is not trivially reversible",
            "the targeted check fails or the intended effect is not observable",
        ],
    },
    "standard": {
        "reasons": [
            "no high-impact signal was declared, but the change is not provably low-impact",
        ],
        "minimum_verification": [
            "focused test or targeted check for the changed unit",
            "regression check of the adjacent behavior the change can reach",
        ],
        "required_records": [
            "task status, changed files and the verification command with its result",
        ],
        "escalate_when": [
            "the change starts to affect data, conclusions, a public interface, security or submission format",
            "the focused check cannot be run in this environment",
        ],
    },
    "strict": {
        "reasons": [
            "at least one high-impact signal, more than five files, or an irreversible change was declared",
        ],
        "minimum_verification": [
            "acceptance evidence bound to the covered artifacts",
            "independent review that does not reuse the implementer's conclusions",
            "re-run after any covered artifact changes",
        ],
        "required_records": [
            "task, decision, verification evidence and review outcome",
            "explicit statement of what remains unverified",
        ],
        "escalate_when": [
            "evidence cannot be bound to a stable revision or covered artifact",
        ],
    },
}


def _signals(value) -> list[str]:
    if type(value) is not list or len(value) > MAX_SIGNALS:
        raise StateError("invalid_input", "signals must be a bounded list")
    seen: list[str] = []
    for signal in value:
        if type(signal) is not str or signal not in ALL_SIGNALS:
            raise StateError("invalid_input", f"unknown signal: {signal!r}")
        if signal not in seen:
            seen.append(signal)
    return sorted(seen)


def _count(value, name: str) -> int:
    if type(value) is not int or not 0 <= value <= 100000:
        raise StateError("invalid_input", f"{name} must be a non-negative integer")
    return value


def infer_signals(paths) -> list[str]:
    """Conservative convenience mapping for the obvious cases only.

    Anything not matched here stays undeclared, which routes to `standard`
    instead of pretending the change is safe.
    """
    if type(paths) is not list or len(paths) > MAX_PATHS:
        raise StateError("invalid_input", "paths must be a bounded list")
    signals = set()
    for path in paths:
        if type(path) is not str or not path.strip():
            raise StateError("invalid_input", "paths must be non-empty strings")
        lowered = path.replace("\\", "/").lower()
        if lowered.endswith((".bib", ".bst", ".cls", ".sty")):
            signals.add("submission-format")
        elif lowered.endswith(".md") and "/docs/" in f"/{lowered}":
            signals.add("docs-only")
    return sorted(signals)


def classify(signals, files_touched: int, reversible: bool = True) -> dict:
    """Map explicit change signals to a routing class with its policy."""
    declared = _signals(signals)
    files = _count(files_touched, "files_touched")
    if type(reversible) is not bool:
        raise StateError("invalid_input", "reversible must be a boolean")
    high = [signal for signal in declared if signal in HIGH_IMPACT]
    low = [signal for signal in declared if signal in LOW_IMPACT]
    if high:
        chosen = "strict"
    elif files > MAX_STANDARD_FILES or not reversible:
        chosen = "strict"
    elif declared and len(low) == len(declared) and files <= MAX_QUICK_FILES:
        chosen = "quick"
    else:
        chosen = "standard"
    reasons = list(POLICY[chosen]["reasons"])
    if high:
        reasons.append("high-impact signals declared: " + ", ".join(high))
    if not reversible:
        reasons.append("the change was declared hard to reverse")
    if files > MAX_STANDARD_FILES:
        reasons.append(f"the change touches {files} files, above the standard ceiling of {MAX_STANDARD_FILES}")
    if not declared:
        reasons.append("no signals were declared, so low risk was not assumed")
    return {
        "class": chosen,
        "signals": declared,
        "files_touched": files,
        "reversible": reversible,
        "reasons": reasons,
        "minimum_verification": list(POLICY[chosen]["minimum_verification"]),
        "required_records": list(POLICY[chosen]["required_records"]),
        "escalate_when": list(POLICY[chosen]["escalate_when"]),
    }


def route(paths, signals=None, files_touched=None, reversible: bool = True) -> dict:
    """Classify from explicit signals, falling back to the conservative inference."""
    declared = _signals(signals) if signals is not None else infer_signals(paths)
    files = len(paths) if files_touched is None else _count(files_touched, "files_touched")
    return classify(declared, files, reversible)


def context(store: Store, task_id: str, budget_bytes: int = DEFAULT_CONTEXT_BUDGET) -> dict:
    """Bounded context package for one task; never silently drops blocking facts."""
    if type(budget_bytes) is not int or not MIN_CONTEXT_BUDGET <= budget_bytes <= MAX_CONTEXT_BUDGET:
        raise StateError(
            "invalid_input",
            f"budget_bytes must be between {MIN_CONTEXT_BUDGET} and {MAX_CONTEXT_BUDGET}",
        )
    task = store.get_task(task_id)
    mandatory = {
        "task": {
            key: task[key] for key in
            ("id", "title", "status", "goal_id", "run_id", "next_action", "summary", "cancel_reason")
        },
        "blocker": task["blocker"],
    }
    optional = {
        "run": task["run"],
        "recent_history": store.history(limit=5),
    }
    def size(value) -> int:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))

    def assembled(body, omitted):
        """Assemble the package with its bookkeeping and its true serialized size."""
        package = dict(body)
        if omitted:
            package["omitted"] = sorted(omitted)
        package["budget"] = {"limit_bytes": budget_bytes, "used_bytes": 0}
        for _ in range(8):
            actual = size(package)
            if package["budget"]["used_bytes"] == actual:
                break
            package["budget"]["used_bytes"] = actual
        return package

    blocking = assembled(mandatory, [])
    if size(blocking) > budget_bytes:
        raise StateError(
            "budget_insufficient",
            f"blocking context for {task_id} needs {size(blocking)} bytes but the budget is {budget_bytes}; "
            "blocking facts are never truncated silently",
        )
    body = dict(mandatory)
    omitted: list[str] = []
    for key, value in optional.items():
        if size(assembled({**body, key: value}, omitted)) > budget_bytes:
            omitted.append(key)
            continue
        body[key] = value
    package = assembled(body, omitted)
    if size(package) > budget_bytes:
        # The omission list is best-effort metadata; blocking facts are already accounted for.
        package = assembled(body, [])
    if size(package) > budget_bytes:
        raise StateError(
            "budget_insufficient",
            f"bounded context for {task_id} needs {size(package)} bytes but the budget is {budget_bytes}; "
            "nothing is truncated silently",
        )
    return package
