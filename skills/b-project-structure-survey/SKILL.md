---
name: b-project-structure-survey
description: "梳理目录结构/工程结构地图/把握工程大局观/模块依赖梳理 · Produce a concise, evidence-grounded static map of an unfamiliar repository's organization: where things live, what depends on what, where boundaries are, and how new code is usually added."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Project Structure Survey

## Purpose and boundary

Produce a cheap, read-only static map of a repository: where things live, what depends on what, where boundaries are, and how similar code is usually organized. This is structural understanding, not system behavior (`a-codebase-onboarding`), source execution teaching (`b-source-code-tutoring`), quality review or implementation planning. Do not automatically hand off to another Skill.

## Survey method: breadth first, limited depth

- Find actual repository/package roots (including monorepo workspaces), languages, top-level responsibilities, manifests, declared entry points, config and test locations. Exclude `.git`, dependency caches, virtual environments, generated/build output and irrelevant vendored code. Use size distribution only if it clarifies scale or module boundaries; state the counting rule if included.
- Use README, package/build declarations, exports, import references and a few structural fragments (module docstrings, entry guards, registration lines) to establish responsibilities and static dependency directions. Do not follow function implementations or business logic. Check evidence from representative modules before generalizing conventions. Show external/generated/dynamic dependencies as unknown when not statically visible.
- Distinguish observed references from architectural constraints: observing `A` imports `B` does not mean the reverse is forbidden. A static import graph is not a runtime call graph or change-impact graph. Public/internal boundaries require evidence from exports, interfaces or explicit documentation; names alone are not proof.
- Stop when the major modules, their relations and extension conventions can be explained. Raise summarization level for large repositories; do not exhaustively enumerate every file or widen into a code audit. If static evidence is insufficient, state "未能从静态结构确认". Use read-only listing/search and small inspection scripts, not project execution, builds, tests or installation.

## Output: compact structural map

Aim for one or two pages when appropriate. Use four views, omitting a view with no relevant evidence:

1. **工程概览** — project type, stack, overall organization and meaningful scale if useful.
2. **模块地图** — trimmed directory tree or module table with one-line evidenced responsibilities; merge minor directories.
3. **结构关系** — observed static directions and confirmed boundaries; qualify unknown or inferred relations.
4. **组织惯例** — where configuration, extension points and tests are organized, based on comparable existing components. Describe conventions, not file-level instructions for a hypothetical task.

No per-file lists, runtime flow, function tutorials, build/deploy guides, refactor recommendations, change plans or scan logs. A diagram is optional, not a substitute for grounded relationships. Do not set a universal scan time or mandatory metrics.

## Delivery and side effects

Default: Markdown in the conversation, no repository or Project Memory writes. Only save the map if the user explicitly requests it and supplies/approves a location; if none is named ask first. Read-only with respect to project code/configuration: do not run the project, modify it, install dependencies or change persistent state just for a survey. The common V2 rules below do not authorize automatic Task/Memory writes by this Skill. If permissions or tooling block inspection, report the limit. Success is an accurate big-picture map with no irrelevant details or unauthorized side effects, not a fixed file count or elapsed time.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
