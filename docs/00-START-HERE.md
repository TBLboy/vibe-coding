# Start Here

## Purpose

This pack defines the smallest useful Vibe Coding V2 baseline for an OpenCode Agent to implement and refine. It is intentionally not a port of any previous framework.

## Canonical source map

| Topic | Canonical source | Other files may do |
|---|---|---|
| Product behavior and three modes | `01-PRODUCT-CONTRACT.md` | Summarize, never redefine |
| Component boundaries | `02-ARCHITECTURE.md` | Describe implementation only |
| State transitions and invariants | `03-STATE-MACHINE.md` + `runtime/core/task-machine.ts` | Add tests; do not invent a second state machine |
| Task data | `04-DATA-CONTRACTS.md` + `schemas/task.schema.json` | Render/read the same fields |
| Project memory and write triggers | `05-MEMORY-CONTRACT.md` + `runtime/core/memory-policy.ts` | Use the same write conditions |
| Main Agent behavior | `runtime/opencode/agents/vibe-main.md` | Concise operational summary |
| Strict reviewer behavior | `runtime/opencode/agents/vibe-reviewer.md` | Same verdicts and retry cap |
| OpenCode APIs and setup | `08-OPENCODE-INTEGRATION.md` | Targeted adapter implementation |
| Acceptance | `09-TEST-MATRIX.md` | Add coverage without weakening invariants |
| Locked choices | `11-DECISIONS.md` | Change only with explicit product approval |

## Build order

1. Verify pure core behavior and contracts.
2. Verify OpenCode plugin loading, mode commands, and storage persistence in the target OpenCode V2 build.
3. Verify the main Agent and reviewer permissions.
4. Verify memory writes and task recovery.
5. Only then implement a conservative installer/package process.

Do not start by building an installer, adding Skills, or adding external integrations. Those are not the core product risk.

## Scope boundary

The first usable version must support:

- session-scoped `/fast`, `/balanced`, `/strict` mode;
- one main Agent and one strict-only read-only reviewer;
- optional Task persistence and a finite strict review loop;
- project-level `AGENTS.md` and `progress.md`, plus Session-specific `current-session.md`;
- risk-appropriate verification and honest delivery reporting.

Anything beyond this list needs a concrete user-facing reason.
