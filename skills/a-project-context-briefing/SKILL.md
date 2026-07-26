---
name: a-project-context-briefing
description: Package a self-contained, evidence-based project or problem brief for another AI, teammate, vendor, forum, or issue tracker without inventing missing context.
license: MIT
compatibility: codex
metadata:
  stage: session-management
  output: external-problem-brief
---

# Project Context Briefing

## Purpose

Prepare another solver to help effectively when context is scattered across the project, logs, configuration, tests, and prior attempts. This packages a problem; it does not substitute for solving it.

## Gather

Read only evidence relevant to the target question: current session, active task, business rules, architecture, exact errors, reproduction steps, affected code/configuration, environment, constraints, and attempts already made. Include full error excerpts where needed and point to larger artifacts by path.

Classify every material statement as **confirmed**, **assumption**, **unknown**, or **need help**. Never fill gaps with plausible details.

## Audience Adaptation

Choose the appropriate form for an AI prompt, teammate handoff, GitHub issue, forum post, vendor request, or expert consultation. State the desired answer and exact decision or diagnosis needed.

## Output

Use this order:

1. Goal and exact question.
2. Relevant system and project background.
3. Expected versus actual behavior.
4. Reproduction and exact evidence.
5. Environment, dependencies, interfaces, and constraints.
6. Attempts and observed results.
7. Unknowns and requested help.

Save a project-facing brief under `.project-log/` when it supports an active task; otherwise return a concise standalone document. Remove secrets and unnecessary personal data before sharing externally.
