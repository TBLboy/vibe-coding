---
name: a-work-trace
description: Record a compact, auditable Context-Hypothesis-Decision-Action-Observation-Result-Lesson chain for meaningful work, so the user's working method can be reviewed and improved without storing verbose hidden reasoning.
license: MIT
compatibility: codex
metadata:
  workflow: trace
  output: work-trace
---

# Work Trace

## Purpose

Leave high-signal evidence of how a work unit evolved, not a transcript of every thought or command.

## Use When

- a non-trivial hypothesis guided implementation or debugging;
- a B/C decision caused a meaningful action;
- expected and actual results differ;
- rework, failure, or a surprisingly effective method produced a lesson;
- the result may improve future workflow.

Do not create trace entries for mechanical edits with no reusable decision value.

## Chain

```text
Context → Hypothesis → Decision → Action → Expected Result
→ Observation → Actual Result → Delta → Lesson → Next Adjustment
```

## Rules

- Summarize rationale in inspectable terms; do not store hidden chain-of-thought.
- Link the relevant task, decision, files, tests, logs, screenshots, or measurements.
- Distinguish what was expected from what actually happened.
- State uncertainty and alternative explanations when causality is weak.
- Mark `knowledge_candidate: true` only when the lesson may generalize.
- A trace entry never automatically changes the constitution or a Skill.

## Output

Append to `.project-log/work-trace/trace.yaml` using the template. Update affected task results and distillation candidates when appropriate.
