---
name: a-project-context-briefing
description: "项目简报/上下文交接/给他人说明 | Package a self-contained, evidence-based project or problem brief for another AI, teammate, vendor, forum, or issue tracker without inventing missing context."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Project Context Briefing

## Mental model

A brief gives another solver enough independent context to answer a specific question without replaying the conversation. Optimize for the recipient's ability to reconstruct the problem, not completeness of project history. Preparing a brief is not solving the problem or authorizing publication.

## Select evidence and adapt to the recipient

- Identify audience (another AI, teammate, vendor, issue tracker, forum or expert), requested diagnosis/decision, relevant scope and permitted disclosure. Read only context needed: current Session/Task if present, applicable project rules, active requirements, progress, code/config, logs/tests, exact errors and prior attempts. Do not assume all these files exist.
- Establish a coherent snapshot: revision/version, environment, relevant input/configuration, expected behavior and its authority, observed behavior, reproduction conditions, exact evidence, constraints and attempts with results. Distinguish present facts from obsolete attempts and known working baselines. Quote the minimal decisive error excerpt; link larger local artifacts by path only if the recipient can access them. Include enough sanitized context to reproduce independently; do not require inaccessible project links to understand the question.
- Separate confirmed facts, assumptions, unknowns and the requested help. Preserve material failed approaches, contradictions and uncertainty, not every operation. If reproduction is unverified or logs are missing, say so rather than inventing a complete sequence.
- For external audiences, minimize and redact credentials, private endpoints/identifiers, personal data and proprietary code beyond authorized scope. Redaction must preserve diagnostic meaning (e.g. consistent placeholders). Do not send, post, upload or change visibility without explicit authorization; preparing a shareable brief is not permission to transmit.

## Deliverable

Lead with goal and exact question, then only relevant system context, expected/actual behavior, reproducible evidence, environment/constraints, prior attempts and unknowns. Adapt to the recipient's format; no compulsory seven-section document for a simple question. Check that a recipient who has not read the conversation can understand the request, distinguish facts from hypotheses, and know what response is needed.

Return a standalone brief; when persistence is useful save under `.vibe/docs/briefs/<topic>.md` or the requested location. Do not paste the full brief into Project Memory. A related Task may reference the brief through a material `record_decision` in prepare/implement when appropriate; otherwise use an existing recovery note only for resumable unfinished work. Do not directly edit registered `nextAction` or create fake Task/Session records merely for a handoff. Follow the actual Runtime lifecycle.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
