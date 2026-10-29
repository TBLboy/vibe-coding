---
name: b-skill-authoring
description: "Design and write a focused V2-compatible OpenCode Skill with clear triggers, progressive disclosure, optional deterministic helpers, and reviewable resource boundaries."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Skill Authoring

## Purpose

Create a new Skill package when a repeatable procedure needs focused instructions or deterministic helpers. A new Skill is incomplete until its `a-*`/`b-*` classification, naming, trigger description, routing decision, and V2 compatibility are explicit.

## Design

Establish the task boundary, triggering requests, inputs, outputs, dependencies, prohibited uses, and validation. Prefer the smallest Skill that owns one coherent job. Keep its description specific enough to route correctly.

## Classification, Naming, and Routing Gate

Before creating files, make and record all five decisions below.

1. **Classify the capability.** Use `a-<kebab-case-name>` only when it is a stable, cross-project, cross-lifecycle method that governs how work is performed or recorded. Use `b-<kebab-case-name>` for a concrete domain, tool, interaction mode, audit, communication pattern, or specialized operation.
2. **Check for overlap and collisions.** Inspect existing `skills/` and the routing table in `runtime/opencode/agents/vibe-main.md`. Extend an existing Skill when the new behavior shares its boundary; do not create a synonym or duplicate capability. The folder name and frontmatter `name` must be identical, lowercase kebab-case, and start with the chosen prefix.
3. **Use the Skill as the entry point.** OpenCode discovers `SKILL.md` directly. A same-named command is optional glue, not a substitute for the Skill contract.
4. **Decide automatic versus explicit routing.** Add a row to the `vibe-main` routing table only when user language can identify the capability reliably, activation is low-risk and low-cost, and loading it does not write external systems, run destructive operations, create broad audits, or create a snapshot/package. Otherwise keep it explicit-only, set `metadata.routing: explicit-only`, and state the reason in the Skill.
5. **Implement and verify the decision.** For an automatic route, add precise trigger wording and the exact Skill name to the routing table. Add the Skill id to the pinned list in `tests/package-shape.test.ts` so the package test guards the Skill, its V2 markers, and its route.

Default safety rule: a vague request never justifies automatically starting a high-cost browser audit, Skill/agent/plugin creation, credential operation, destructive action, or irreversible change. Require an explicit user request for those operations.

## V2 compatibility contract

Every Skill must:

- carry `metadata.v2: true` in frontmatter;
- end with the standard "V2 operating rules" section (copy it from any existing Skill);
- persist durable state only in the V2 locations: Task JSON under `.vibe/tasks/`, `.vibe/progress.md`, the Session's `current-session.md`, optional per-work baselines under `.vibe/requirements/`, and the project `AGENTS.md`;
- never invoke `vibe-reviewer` itself; review belongs to the strict gate owned by the main Agent;
- describe only positive V2 guidance — do not include sentences about retired frameworks or forbidden legacy terms.

## Package

Create under the framework source tree, then install with the V2 installer:

```text
skills/<a-or-b-kebab-case-name>/
├── SKILL.md
├── REFERENCE.md      # only for rarely needed detail
├── EXAMPLES.md       # only when examples clarify behavior
├── templates/        # only for files the Skill must reproduce verbatim
└── scripts/          # only for deterministic repeated operations (no third-party dependencies)
```

Keep `SKILL.md` concise but complete: method, rules, outputs, completion gate. Put required frontmatter first: `name`, trigger-focused `description`, `license`, `compatibility`, and metadata. Do not embed time-sensitive facts, secrets, personal paths, or unrelated project state. Scripts referenced by the Skill must resolve from `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/skills/<name>/...`, and each script needs a test under `scripts/test_*.py` or an explicit reason it cannot be tested.

## Review

Verify the trigger description, terminology, input/output contract, normal and boundary flows, tool assumptions, safety constraints, and at least one evaluation example. Also verify:

- `a-*` or `b-*` classification and reasoning are explicit;
- folder and frontmatter names match with no collision;
- automatic or explicit-only routing has an explicit decision and rationale;
- `vibe-main.md` and `tests/package-shape.test.ts` were updated when the routing decision requires it;
- `npm run test:core` and the installer tests pass, and the installed copy matches the source.

Keep references one level deep. Review the diff before installing or promoting a Skill.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
