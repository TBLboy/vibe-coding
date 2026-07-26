---
name: b-plan-stress-test
description: Stress-test a proposed plan or design through one focused question at a time, resolving decision dependencies with evidence and a recommended answer.
license: MIT
compatibility: codex
metadata:
  type: decision-skill-pack
  output: resolved-design-questions
---

# Plan Stress Test

## Purpose

Use when the user asks to be grilled, wants a plan pressure-tested, or needs to uncover missing design decisions before committing.

## Method

1. Read available project facts and inspect the codebase before asking anything discoverable.
2. Map the plan's goals, actors, interfaces, states, dependencies, failure paths, constraints, security, cost, operational ownership, and rollback.
3. Ask one highest-impact unresolved question at a time.
4. Give a recommended answer, its impact, and the evidence or assumption behind it.
5. Follow dependent branches until the plan has a coherent decision path.

Do not turn ordinary implementation choices into an endless interview. Record material B-level decisions and stop for C-level product, safety, data, public-interface, cost, or irreversible architecture decisions.

## Output

Maintain a compact decision list: question, options, recommendation, chosen answer, owner, and remaining risk. Update `.project-log/decisions/decision-log.yaml` and active tasks when the plan belongs to an active project.
