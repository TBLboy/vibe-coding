---
name: b-skill-authoring
description: "写Skill/做技能 | Create or refine a focused V2-compatible OpenCode Skill that adds domain expertise, routes accurately, uses progressive disclosure, and has observable quality checks."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Skill Authoring

## Purpose and mental model

A Skill supplies reusable domain expertise that the base model and Main Agent may not reliably apply on their own. It is not a persona, general engineering checklist, or mandatory workflow stage. Create or refine one only for a real recurring need or specialist capability; identify what it improves and when it should remain unloaded. Prefer extending an existing coherent Skill over a synonym or duplicate. If the model, existing Skill, or a simple instruction already solves the need reliably, do not create another Skill.

## Design for professional value

Select the following design dimensions as relevant; they are not mandatory headings or a fixed procedure.

- **Scope:** name the job, triggering intent, inputs, exclusions and neighboring capabilities. Give the Skill one coherent responsibility, with a useful result even when used independently.
- **Mental model:** express what experts pay attention to in this domain: important relationships, invariants, failure modes and reasons for decisions. Avoid generic exhortations already covered by Main Agent.
- **Method:** supply actionable domain heuristics, evidence to inspect, decision criteria, trade-offs, and techniques the model might otherwise miss. Use specific examples or counterexamples when they change a decision; do not turn every method into a compulsory sequence.
- **Quality and constraints:** preserve necessary safety gates, authority, failure handling and evidence requirements. Match freedom to risk: flexible principles for judgment-heavy work; precise steps, parameters and checks for deterministic or fragile operations. Verify that tools and interfaces actually exist.
- **Outcome:** define observable results and completion criteria, including partial or blocked outcomes. Scale investigation, output and verification to the task; do not require a full template for a small job.

Ground domain methods in actual project evidence or reliable specialist sources when uncertainty warrants research. Distinguish facts, recommendations and assumptions; do not import whole external playbooks or unverified practices. Ask of each passage: what useful decision or behavior would be lost if it were removed? Merge duplicate rules, remove filler and speculative procedures, and preserve indispensable specialist knowledge. Optimize information value, not a fixed length or compression target.

## Progressive disclosure

- `description`: a compact discovery contract in the user's language first; distinguish trigger, intent, and nearby non-triggers where important. Do not duplicate the body or advertise unavailable capabilities.
- `SKILL.md`: self-contained core method, judgment criteria, essential boundaries and completion standard. Keep safety-critical rules here; do not hide them behind optional reading.
- References or examples: move detailed, low-frequency knowledge, variants and worked cases out of the main path. Link each from the relevant decision point; read only when needed, keep references one level deep, and avoid duplicate sources of truth. Do not reload an unchanged Skill or reference while its applicable instructions remain available; reacquire after context loss or change.
- Scripts/templates: use only for real deterministic repetition or exact artifacts; verify failure behavior and dependencies. Do not add code, resources, or new tools merely to make a Skill look complete.

Main Agent owns general engineering judgment; Skills own domain methods; Runtime owns enforceable lifecycle and Policy; Project Memory owns project facts. Refer to the authority instead of duplicating its rules. Keep environment-specific values and secrets outside the distributed Skill; discover actual configuration and verify time-sensitive capabilities when needed.

## Classification, naming and routing gate

Before creating files, make these decisions (record only at the depth the current task warrants):

1. **Classify:** `a-<kebab-case-name>` for stable, cross-project, cross-lifecycle engineering methods; `b-<kebab-case-name>` for concrete domains, tools, interaction modes, audits, communication patterns or specialized operations.
2. **Check overlap:** inspect `skills/` and `runtime/opencode/agents/vibe-main.md`; extend an existing coherent capability if possible. Folder and frontmatter `name` must match, lowercase kebab-case with the chosen prefix.
3. **Entry point:** OpenCode discovers `SKILL.md` directly; a same-named command is optional glue, not a replacement.
4. **Routing:** infer activation only when intent is reliably identifiable, low-risk and low-cost. High-cost audits, snapshots, Skill/agent/plugin creation, credential operations, external writes, destructive or irreversible changes require explicit user intent and separate authorization where needed. For explicit-only capabilities set `metadata.routing: explicit-only` and state why. In the current managed pack, retain an explicit named trigger row with its guard (the package tests require a row for every managed Skill); explicit-only never means broad inferred activation. Changing that managed routing contract requires a separate approved decision.
5. **Integrate:** use Chinese/user-language aliases first in both the description and the managed routing row, with the exact Skill ID and applicable qualifiers. Update the pinned list in `tests/package-shape.test.ts` for additions/removals and protect existing routes. A matched route authorizes loading the method, not its side effects.

## V2 compatibility contract

Every managed Skill must:

- carry `metadata.v2: true`, and end with the standard `V2 operating rules` section (use this Skill's compact footer verbatim; retain indispensable domain constraints in its body);
- follow `docs/05-MEMORY-CONTRACT.md` for durable state: `AGENTS.md`, `.vibe/progress.md`, `sessions/`, `tasks/`, `requirements/`, `lessons/`, and `docs/` under the resolved memory root as applicable; use Runtime events for registered Tasks and obtain user approval before changing project rules;
- never invoke `vibe-reviewer` itself; the strict gate belongs to Main Agent;
- describe positive V2 guidance without introducing retired objects, extra lifecycle stages or parallel persistence.

## Package

Create under the framework source tree and distribute with the existing V2 installer. Use only the resources needed by the capability:

```text
skills/<a-or-b-kebab-case-name>/
├── SKILL.md
├── references/      # optional targeted depth, directly linked
├── EXAMPLES.md      # optional decision-changing examples
├── templates/       # optional exact artifacts
└── scripts/         # optional deterministic helpers
```

Frontmatter: `name`, trigger-focused `description`, `license`, `compatibility`, and metadata. No new third-party dependency without approval. Script paths must resolve from `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/skills/<name>/...`; provide a test under `scripts/test_*.py` or an explicit reason it cannot be tested.

## Review and refinement

Check relevance, distinct scope, discoverability, domain value, freedom appropriate to risk, executable instructions, safe authority and observable outputs. Inspect the diff: preserve useful methods, domain safety, referenced resources and existing trigger coverage; avoid edits based on length alone.

Use representative positive, near-miss and boundary/failure scenarios as applicable. For prompt quality, compare the same task with Main Agent alone, the previous Skill (when refining), and the candidate Skill, keeping model, project, Policy and tools fixed where feasible. Inspect decisions, actual work and verification, not just polished prose or length. Use existing evaluations or small manual trials; do not create an evaluation platform. If the real host/model cannot be run, report that limitation separately from static checks.

Verify naming, V2 markers, routing decisions, links, helpers and installed bytes. Run `npm run test:core` and the installer tests; update relevant tests/docs when the contract changes. Do not claim better model behavior from structural tests alone. Promote the Skill when its demonstrated value justifies its context cost, with outstanding behavioral validation made explicit.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
