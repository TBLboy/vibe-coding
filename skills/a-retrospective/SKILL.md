---
name: a-retrospective
description: Review a completed increment's decisions, actions, results, failures, rework, validation quality, and workflow friction, then create concrete improvement actions and evidence-backed knowledge candidates.
license: MIT
compatibility: codex
metadata:
  stage: retrospective
  output: retrospective-record
---

# Retrospective

## Purpose

Improve the working system, not merely summarize what happened.

## Review Dimensions

- Was the business problem clarified at the right depth?
- Which assumptions caused rework?
- Were questions asked too early, too late, or unnecessarily?
- Did the authority matrix produce the right level of autonomy?
- Were technical options researched proportionally?
- Were tasks vertically sliced and independently verifiable?
- Did engineering specs remove useful ambiguity without over-constraining implementation?
- Which tests detected defects, and which defects escaped?
- Where did code, business logic, and tests drift?
- Which tools, Skills, Agents, or project-log fields created friction?
- What should be repeated, stopped, or changed next time?

## Evidence

Use task durations/status transitions when available, decision outcomes, failed attempts, alignment findings, test evidence, user corrections, and incident/debugging records.

Do not convert a personal impression into a universal rule without evidence.

## Outputs

Write `.project-log/retrospective/retrospective.yaml` with:

- scope and outcome;
- what worked;
- what failed or caused rework;
- root causes;
- workflow observations;
- concrete improvement actions;
- candidate insights for distillation;
- evidence and confidence.

Create tasks for actionable process/tooling changes.
