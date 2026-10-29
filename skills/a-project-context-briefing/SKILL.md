---
name: a-project-context-briefing
description: "Package a self-contained, evidence-based project or problem brief for another AI, teammate, vendor, forum, or issue tracker without inventing missing context."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Project Context Briefing

## Purpose

Prepare another solver to help effectively when context is scattered across the project, logs, configuration, tests, and prior attempts. This packages a problem; it does not substitute for solving it.

## Gather

Read only evidence relevant to the target question: the current Session's `current-session.md`, the active Task JSON, `AGENTS.md`, `.vibe/progress.md`, business rules, architecture, exact errors, reproduction steps, affected code/configuration, environment, constraints, and attempts already made. Include full error excerpts where needed and point to larger artifacts by path.

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

Return the brief as a standalone document; save it as `.vibe/docs/briefs/<topic>.md` when it should persist, or where the user asks. If the brief supports an active Task, reference its location from the Task `nextAction` or the Session's `current-session.md`; do not paste it into project memory. Remove secrets and unnecessary personal data before sharing externally.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
