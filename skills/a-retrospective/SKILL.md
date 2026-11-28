---
name: a-retrospective
description: "复盘/总结这次 | Review a completed increment's decisions, actions, results, failures, rework, validation quality, and workflow friction, then create concrete improvement actions and evidence-backed knowledge candidates."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Retrospective

## Mental model

Improve the working system by reconstructing why an outcome occurred, not by replaying actions or assigning blame. Compare intended behavior, constraints and expected results with actual implementation, verification, user feedback and residual risk. A retrospective can cover a completed increment or a bounded incident; do not fabricate completion for unfinished work.

## Investigate causes and improvement opportunities

Use relevant Task decisions, verification/review findings and repair rounds if present, Git diff/history, tests, failed attempts, user corrections, alignment findings and incident evidence. Distinguish observed symptom, immediate trigger, causal mechanism and contributing conditions. Trace back to the earliest decision or missing signal that could reasonably have prevented the problem. Consider alternative causes and whether evidence supports them; avoid hindsight bias and universal rules inferred from one incident.

Select review dimensions that matter: business understanding/assumptions, A/B/C authority and question timing, technical research/spec/decomposition, implementation and preserved behavior, tests that caught or missed defects, mode/risk/reviewer value, tool/Skill/Memory friction and unnecessary rework. Also identify practices that demonstrably worked and should be repeated. Compare costs and benefits of a proposed process change; do not add a gate just because a mistake occurred.

## Useful outputs and knowledge

Report outcome, evidence-backed successes/failures, causes and confidence, and a small set of concrete improvements. Each proposed action should address a specific cause, have a trigger/owner where useful, and a way to observe whether it helps. Distinguish actions approved for implementation from suggestions; retrospective alone does not authorize code, Skill, policy or configuration edits.

For durable lessons, follow `docs/05-MEMORY-CONTRACT.md`: use `.vibe/lessons/<id>.md` and its index for reusable bug/correction knowledge, including symptom, cause/fix when known, context/conditions, prevention principle and evidence; avoid claiming an unresolved cause as fact. Find and merge similar lessons, accumulating occurrences rather than duplicating. Preserve the existing bug registration and automatic verbal-correction rules; at three occurrences propose distillation into `AGENTS.md`, never edit it without user approval. A severe or broadly applicable evidence-backed lesson can warrant an earlier proposal. Count distinct incidents, not mentions; search the index first, update status/keywords/summary when the lesson changes and preserve prior evidence. Use `.vibe/progress.md` for durable milestones, decisions and material limitations, not a duplicate lesson log. Surface framework defects to the user. Create a Task only when an authorized improvement actually needs persistent tracking and starts under the existing Policy.

Completion is actionable learning with evidence and scope, not a mandatory report or a claim that every recommendation was implemented.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
