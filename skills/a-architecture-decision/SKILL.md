---
name: a-architecture-decision
description: Convert an approved requirement baseline and technical recommendation into explicit module boundaries, interfaces, data flows, failure handling, operational constraints, and recorded architecture decisions.
license: MIT
compatibility: codex
metadata:
  stage: architecture-decision
  output: architecture-baseline
---

# Architecture Decision

## Purpose

Define only the architecture necessary for the current increment. Avoid both accidental architecture and speculative over-design.

## Inputs

- active requirement baseline;
- active atomic business logic;
- solution-research results;
- current codebase and constraints;
- active technical decisions.

## Required Views

Describe, at the minimum useful depth:

1. **Responsibilities** — modules/services/nodes and what each owns.
2. **Interfaces** — APIs, events, topics, actions, files, schemas, or device boundaries.
3. **Data flow** — source, transformations, ownership, persistence, and destinations.
4. **State and concurrency** — state owner, synchronization, lifecycle, retries, idempotency.
5. **Failure behavior** — detection, containment, recovery, user-visible result, logging.
6. **Security and privacy** — trust boundaries, permissions, secrets, sensitive data.
7. **Observability** — logs, metrics, traces, health indicators, diagnostics.
8. **Deployment and compatibility** — environments, versions, hardware, migration, rollback.

## Decision Discipline

- Record material choices as decision-log entries.
- Prefer reversible boundaries and narrow adapters around external dependencies.
- Do not let a framework dictate product behavior.
- Use C authority for irreversible, externally visible, security-sensitive, costly, or migration-heavy decisions.
- Mark hypotheses that require a spike; do not disguise them as settled architecture.

## Output

Update `.project-log/architecture/architecture.yaml` and related decision records.

Architecture entries should reference the business atoms they support and the decisions that justify them.

## Completion Gate

- ownership and interfaces are unambiguous;
- critical data and failure paths are described;
- external dependencies are isolated behind defined boundaries where practical;
- high-impact decisions are approved;
- the architecture is sufficient for task decomposition without inventing new product behavior.
