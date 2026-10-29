---
name: a-retrospective
description: "Review a completed increment's decisions, actions, results, failures, rework, validation quality, and workflow friction, then create concrete improvement actions and evidence-backed knowledge candidates."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Retrospective

## Purpose

Improve the working system, not merely summarize what happened.

## Review Dimensions

- Was the business problem clarified at the right depth?
- Which assumptions caused rework?
- Were questions asked too early, too late, or unnecessarily?
- Did the A/B/C authority split produce the right level of autonomy?
- Were technical options researched proportionally?
- Were tasks vertically sliced and independently verifiable?
- Did engineering specs remove useful ambiguity without over-constraining implementation?
- Which tests detected defects, and which defects escaped?
- Where did code, business logic, and tests drift?
- Which tools, Skills, Agents, Task fields, or memory files created friction?
- Was the Session policy (fast/balanced/strict) appropriate for the risk; did strict review add value?
- What should be repeated, stopped, or changed next time?

## Evidence

Use the completed Task JSON (decisions, verification, review findings, repair rounds), Git history, failed attempts, alignment findings, test evidence, user corrections, and incident/debugging records.

Do not convert a personal impression into a universal rule without evidence.

## Outputs

Return the retrospective covering:

- scope and outcome;
- what worked;
- what failed or caused rework;
- root causes;
- workflow observations;
- concrete improvement actions;
- candidate insights worth keeping;
- evidence and confidence.

Persist only durable results: project-level lessons and limitations into `.vibe/progress.md`; stable, actionable rules into the project `AGENTS.md` project-level rules; framework defects into `.vibe/progress.md` "Known limitations" and the user's attention. Create a Task only for an improvement action that needs persistent tracking.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
