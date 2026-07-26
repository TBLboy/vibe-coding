---
name: a-loop-control
description: Control a bounded Vibe work loop through durable state restoration, evidence validity, failure attribution, retry contracts, native Codex Goal synchronization, completion evaluation, and handoff.
license: MIT
compatibility: codex
metadata:
  stage: loop-control
  output: loop-decision
---

# Loop Control

## Purpose

Use the installed `loopctl` runtime as the single deterministic controller for Project Goal state, evidence validity, failure attribution, retry limits, native Goal synchronization, and Handoff.

Codex's native `/goal` is the only thread execution and continuation controller. This Skill must not create a second continuation loop.

## Restore

At the start of non-trivial work:

```bash
VIBE_RUNTIME="${CODEX_HOME:-$HOME/.codex}/vibe-workflow"
python3 "$VIBE_RUNTIME/scripts/loopctl.py" --root <project-root> --json restore
```

On Windows use `py -3`.

Read the Project Goal, active run, current task, valid/stale evidence, open C-level questions, limits, and exact next action before changing product files.

## Native Goal Bridge

Generate the objective to bind through Codex's native `/goal`:

```bash
python3 "$VIBE_RUNTIME/scripts/loopctl.py" --root <project-root> --json goal-bind
```

Synchronize observed native Goal state with `goal-sync`. Native Goal completion only triggers Project Goal evaluation; it does not bypass required evidence.

## Decision Boundary

Create a formal Loop Decision only at task start/switch, verification completion, reviewer completion, phase exit, blocking, limit reached, C-level user decision, Goal evaluation, or Handoff.

Every failure decision records:

- observed evidence;
- `failure_origin`;
- failure signature;
- whether new information was produced;
- one explicit next action.

Allowed failure origins:

- `implementation`
- `specification`
- `task-decomposition`
- `technical-selection`
- `functional-business-logic`
- `technical-business-logic`
- `environment`
- `verification-harness`
- `unknown`

## Retry Contract

`retry-current-task` requires:

- a falsifiable `hypothesis`;
- a concrete `delta`;
- expected new evidence.

Never repeat the same failure signature with the same delta. When limits are reached, return upstream, perform targeted research, or generate Handoff.

## Evidence

Register evidence with `record-evidence`. Any covered code, config, dependency, requirement, or verification-harness change makes the evidence `stale`; never delete it to hide invalidation.

## Completion

Run:

```bash
python3 "$VIBE_RUNTIME/scripts/loopctl.py" --root <project-root> --json evaluate goal
```

Project Goal completion requires all success conditions, valid required evidence, no blocking C-level question, and independent review evidence for high/critical goals.
