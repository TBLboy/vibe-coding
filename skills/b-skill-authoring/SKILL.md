---
name: b-skill-authoring
description: Design and write a focused Codex Skill with clear triggers, progressive disclosure, optional deterministic helpers, and reviewable resource boundaries.
license: MIT
compatibility: codex
metadata:
  type: authoring-skill-pack
  output: draft-skill-package
---

# Skill Authoring

## Purpose

Create a new Skill package when a repeatable procedure needs focused instructions or deterministic helpers. For promoting an approved project lesson into the workflow, first use `a-skill-evolution`. A new Skill is incomplete until its `a-*`/`b-*` classification, naming, trigger description, and routing decision are explicit.

## Design

Establish the task boundary, triggering requests, inputs, outputs, dependencies, prohibited uses, and validation. Prefer the smallest Skill that owns one coherent job. Keep its description specific enough to route correctly.

## Classification, Naming, and Routing Gate

Before creating files, make and record all five decisions below.

1. **Classify the capability.** Use `a-<kebab-case-name>` only when it is a stable, cross-project, cross-lifecycle framework method that governs how work is performed or recorded. Use `b-<kebab-case-name>` for a concrete domain, tool, interaction mode, audit, communication pattern, or specialized operation.
2. **Check for overlap and collisions.** Inspect existing `skills/` and Vibe Coding main-agent routing. Extend an existing Skill when the new behavior shares its boundary; do not create a synonym or duplicate capability. The folder name and frontmatter `name` must be identical, lowercase kebab-case, and start with the chosen `a-` or `b-` prefix.
3. **Use the Skill as the entry point.** Codex discovers `SKILL.md` directly. Do not require an OpenCode-style same-named command file.
4. **Decide automatic versus explicit routing.** Add a Vibe Coding main-agent routing rule only when user language can identify the capability reliably, activation is low-risk and low-cost, and loading it does not write external systems, mutate a knowledge base, run destructive operations, create broad audits, or create a snapshot/package. Otherwise keep it explicit-only and state the reason in the Skill.
5. **Implement and verify the decision.** For an automatic route, add precise intent/trigger wording and the exact Skill name under `## Skill 路由` in the global main-agent prompt. Verify the route refers to an existing Skill. Update the resource snapshot after installation so the new capability migrates with the current Vibe Coding resource set.

Default safety rule: a vague request never justifies automatically starting a high-cost browser audit, external knowledge-base operation, Skill/agent/plugin creation, migration snapshot, credential operation, destructive action, or irreversible change. Require an explicit user request for those operations.

## Package

Create under the current Vibe Coding resource tree:

```text
~/.config/codex/skills/<a-or-b-kebab-case-name>/
├── SKILL.md
├── REFERENCE.md      # only for rarely needed detail
├── EXAMPLES.md       # only when examples clarify behavior
└── scripts/          # only for deterministic repeated operations
```

Keep `SKILL.md` concise. Put required frontmatter first: `name`, trigger-focused `description`, `license`, `compatibility`, and metadata. Do not embed time-sensitive facts, secrets, personal paths, or unrelated project state.

When editing the source workflow package, add the Skill under `skills/<name>/SKILL.md`, then install or safely update the global resource tree.

## Review

Verify the trigger description, terminology, input/output contract, normal and boundary flows, tool assumptions, safety constraints, and at least one evaluation example. Also verify:

- `a-*` or `b-*` classification and reasoning are explicit;
- folder and frontmatter names match with no collision;
- automatic or explicit-only routing has an explicit decision and rationale;
- Vibe Coding 主代理 was updated when the routing decision requires it;
- the installed resource snapshot contains the final Skill and routing file.

Keep references one level deep. Review the diff before installing or promoting a Skill.
