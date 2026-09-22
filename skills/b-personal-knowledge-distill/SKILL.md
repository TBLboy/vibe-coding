---
name: b-personal-knowledge-distill
description: Curate approved, evidence-backed project lessons into a separate personal knowledge base with staged drafts, duplicate checks, provenance, review, and controlled synchronization.
license: MIT
compatibility: codex
metadata:
  type: personal-knowledge-skill-pack
  output: knowledge-base-update-proposal
---

# Personal Knowledge Distill

## Purpose

Move validated reusable knowledge from a project's `.project-log/` into a separate knowledge base without copying project noise or silently changing either repository.

## Preconditions

Use an explicitly configured knowledge-base repository and its normal authentication. Do not hard-code local paths, proxy addresses, credentials, or remote URLs into this Skill. If the repository is unavailable, report it and ask before initialization or cloning.

## Workflow

1. Read project records and candidates before scanning code.
2. Keep only reusable, evidence-backed lessons with applicability, exclusions, confidence, and source references.
3. Compare against existing knowledge to classify each proposal as add, update, merge, or discard.
4. Write drafts to a reviewable staging area; never modify formal knowledge during scan or draft.
5. Apply only approved changes, preserving provenance to project evidence.
6. Synchronize raw project records only when explicitly requested and under a documented retention policy.

## Boundaries

`a-codebase-extraction` discovers lessons; `a-operator-distill` governs their promotion; this Skill curates approved knowledge into the external personal repository. Never treat a one-off note, transient preference, secret, or project-local identifier as portable knowledge.
