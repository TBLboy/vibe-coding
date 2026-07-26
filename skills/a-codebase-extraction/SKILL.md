---
name: a-codebase-extraction
description: Extract reusable architecture patterns, debugging lessons, engineering knowledge, and future improvements from a mature codebase or completed milestone with evidence and applicability boundaries.
license: MIT
compatibility: codex
metadata:
  stage: retrospective
  output: reusable-project-lessons
---

# Codebase Extraction

## Purpose

Turn a mature codebase or completed milestone into reusable engineering knowledge. This is not a file summary and does not replace implementation work.

## Inputs

Read relevant `.project-log/` facts first when present, then inspect code, tests, configuration, changelog, incidents, and verification evidence. Distinguish confirmed outcomes from inference.

## Extraction

Capture only evidence-backed lessons about:

- business flows and reusable task patterns;
- architecture boundaries, data flow, interfaces, and deployment;
- external tools and why they succeeded or failed;
- debugging symptoms, root causes, failed attempts, fixes, and earlier detection;
- configuration, observability, runtime, and operational lessons;
- personal engineering practices worth repeating or avoiding.

For every lesson, state its source evidence, applicable context, exclusions, confidence, and proposed reuse target. Do not promote a one-off coincidence into a general rule.

## Outputs

Update `.project-log/retrospective/retrospective.yaml` with the project-specific review. Create candidates in `.project-log/distillation/candidates.yaml` only for reusable lessons that meet the `a-operator-distill` promotion rules. Use `b-personal-knowledge-distill` only when the user wants an approved candidate curated into a separate personal knowledge base.

## Completion Gate

- project conclusions are traceable to evidence;
- lessons explain why they matter, not merely what files exist;
- project-local observations remain separate from reusable candidates;
- unknowns and unfinished work are explicit.
