---
name: a-loop-control
description: Control a bounded Vibe work loop through durable state restoration, evidence validity, failure attribution, retry contracts, Project Goal evaluation, and handoff.
license: MIT
compatibility: opencode
metadata:
  stage: loop-control
  output: loop-decision
---

# Loop Control

## Purpose

Use the installed `vibe` runtime as the deterministic controller for Project Goal state, evidence validity, failure attribution, retry limits, and Handoff. `loopctl` remains the compatibility entry for legacy-format projects.

Project Goal is the only completion contract. The session-level Goal control surface is the pinned
`@prevalentware/opencode-goal-plugin@0.1.51` (`/goal`, `/pause_goal`, `/resume_goal`); its state is a
session control surface and never counts as completion evidence. This Skill must not invent or call
any other continuation interface. If the plugin is absent or disabled, continuation falls back to
explicit user turns plus the restored `.project-log` state and Handoff.

## Restore

At the start of non-trivial work:

```bash
VIBE_CONFIG="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
VIBE_RUNTIME="${VIBE_RUNTIME:-$VIBE_CONFIG/vibe-workflow}"
VIBE_PYTHON="${VIBE_PYTHON:-$(cat "$VIBE_CONFIG/vibe-python")}"
"$VIBE_PYTHON" "$VIBE_RUNTIME/scripts/vibe.py" --root <project-root> status
```

Read the Project Goal, active run, current task, valid/stale evidence, open C-level questions, limits, and exact next action before changing product files.

For a legacy-format project, use `loopctl.py --root <project-root> --json restore` instead.

## Session Continuation

At the start of a turn, restore the Project Goal, active Run, task status, valid evidence, blocking questions and exact next action. Continue until the task is complete, explicitly blocked, or the user pauses.

Do not claim automatic continuation, background resumption, or a session Goal binding that the installed OpenCode version does not provide. When TASK-072 ships a session runner, this section must be updated from the actual implemented interface before use.

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
"$VIBE_PYTHON" "$VIBE_RUNTIME/scripts/loopctl.py" --root <project-root> --json evaluate goal
```

Project Goal completion requires all success conditions, valid required evidence, no blocking C-level question, and independent review evidence for high/critical goals.
