# Vibe Coding V2 — Engineering Pack

> Status: clean-room rewrite baseline + small executable core reference. Core tests pass; OpenCode 2.0.29 plugin loading, mode-command registration, and a queued `/fast` Session smoke pass in an isolated profile. Provider-dependent continuation, strict reviewer enforcement, and installation remain unaccepted.

Vibe Coding V2 is a deliberately small, policy-driven framework for OpenCode. It preserves useful engineering discipline while removing mandatory process ceremony.

## The model

```text
Session + Policy
       ↓
Understand what matters
       ↓
Plan only when useful
       ↓
Implement → Verify → (Strict review only) → Deliver
       ↓
Persist durable facts only
```

Four concepts only:

- **Session** — user-facing context and current mode.
- **Policy** — `fast`, `balanced` or `strict`; controls process depth.
- **Task** — optional persistent work unit; always created in strict mode.
- **Project Memory** — project rules and durable facts, not an action transcript.

## Non-negotiable decisions

- No compatibility with, or migration from, any previous framework.
- No independent reviewer toggle. `fast` and `balanced` never invoke the reviewer; `strict` requires reviewer `go` before Task completion.
- Task policy is frozen when the Task starts; changing Session mode affects new work only.
- No Goal runtime, Run state machine, event-sourced operation ledger, SQLite projection, standalone Evidence model, default MCPs or third-party workflow plugins.
- No logs for file reads, searches, shell commands, ordinary retries or intermediate actions.
- Each Session has its own `current-session.md` for resumable unfinished work/blockers; project-level `progress.md` is for durable facts. Neither is rewritten for every action by ritual.
- Core tests have no third-party package dependency.

## Start here

Release status and verified boundaries: [`RELEASE_NOTES.md`](RELEASE_NOTES.md).

1. Read [`AGENTS.md`](AGENTS.md) before modifying this package.
2. Read [`docs/00-START-HERE.md`](docs/00-START-HERE.md).
3. Treat [`docs/01-PRODUCT-CONTRACT.md`](docs/01-PRODUCT-CONTRACT.md) and [`docs/11-DECISIONS.md`](docs/11-DECISIONS.md) as the approved product baseline.
4. Use the state/data/memory/prompt/test documents as implementation contracts.
5. Use the conservative V2 installer only after reviewing the live integration limits below; do not claim production readiness until the full checklist passes.

## Layout

```text
AGENTS.md                         Instructions for the agent refining this package
README.md                         Overview and handoff entry point
docs/                             Canonical product and engineering contracts
schemas/task.schema.json          Minimal persisted Task shape
runtime/core/                     Small pure TypeScript reference logic
runtime/opencode/                 OpenCode config, plugin adapter, Agent prompts
skills/                           Managed V2 capability Skills (a-project-init carries the AGENTS.md/memory templates)
tests/                            Core behavior tests
```

## Run core tests

Requires Node.js 22.6 or newer (for built-in TypeScript type stripping):

```bash
npm run test:core
```

This validates the pure policy/state-machine/review-authorization reference logic. It does **not** prove that the plugin loads in your exact OpenCode build. `npm run verify` runs the core tests plus the Python installer/Skill tests; `npm run typecheck:core` fetches TypeScript on demand via `npm exec` (no project dependency). Follow [`docs/08-OPENCODE-INTEGRATION.md`](docs/08-OPENCODE-INTEGRATION.md) and the smoke-test matrix before installing globally.

## Install V2

The bundled installer owns only V2 runtime files, the two V2 Agents, the V2
plugin entry, and its own state file. It preserves existing model, provider,
MCP, credential, and unrelated plugin configuration. It creates a timestamped
backup beneath the target OpenCode config directory before every write.

```powershell
python scripts/vibe_v2_installer.py install --root .
python scripts/vibe_v2_installer.py verify --root .
python scripts/vibe_v2_installer.py uninstall
```

Use `--opencode-home <path>` to test against an isolated profile. `uninstall`
removes only unchanged files whose hashes still match V2 ownership; modified
files are preserved. It restores the plugin/default-agent configuration only
when V2 originally added or replaced it.

The installer has been exercised against OpenCode 2.0.29 for plugin loading and
mode-command registration, and the local OpenCode 2.0.32 control layer passed
provider-backed `/fast` and strict-review positive-path smoke tests.
Compaction/reopen persistence, cross-Session behavior, and negative reviewer
permission cases remain acceptance work; see [`VERIFICATION.md`](VERIFICATION.md).

## What this package intentionally does not include

No legacy upgrade/uninstall scripts, compatibility shims, old-state migration, third-party MCP definitions, provider/model configuration, Goal plugin, SQLite, operation ledger, empty evidence/review records, or large library of lifecycle slash commands. These are not missing features; they are excluded from the new baseline.

## Optional V2 capability Skills

The V2 installer includes a user-approved, managed capability pack under `skills/`. These Skills restore focused abilities such as codebase onboarding, clarification, architecture/specification, implementation, verification, research, code tutoring, model configuration, UX audit, and plan stress testing. `vibe-main` contains the trigger routing table. They are V2-compatible: they use `AGENTS.md`, `.vibe` memory, and optional Task JSON only; they do not recreate the old Project Log, Goal, Run, ledger, SQLite, standalone Evidence, or dynamic subagent architecture.
