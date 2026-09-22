---
name: a-skill-evolution
description: Convert an approved, repeated, evidence-backed operator lesson into a minimal constitution, Agent, Skill, template, plugin, or evaluation change and test it before promotion.
license: MIT
compatibility: codex
metadata:
  stage: distillation
  output: encoded-asset
---

# Skill Evolution

## Purpose

Turn validated experience into durable capability without fossilizing one-off behavior.

## Preconditions

- an approved candidate exists in `.project-log/distillation/candidates.yaml`;
- applicability, exclusions, evidence, risk, and target asset are explicit;
- conflicts with higher-priority rules have been checked.

## Target Selection

- stable invariant → constitution;
- role/orchestration behavior → Agent;
- repeatable procedure → Skill;
- recurring artifact structure → template/schema;
- deterministic automation → script/plugin;
- domain-specific capability → Skill Pack.

## Procedure

1. Write the smallest patch that encodes the lesson.
2. Add normal, boundary, conflict, and non-trigger evaluation cases under `.project-log/evals/`.
3. Validate Skill name/frontmatter and all affected schemas/config.
4. Compare behavior before and after the patch.
5. Record counterexamples and rollback conditions.
6. Apply only after approval required by the candidate.
7. Keep the old version in backup/version control.

Never let a newly encoded Skill rewrite its own approval or evaluation rules.
