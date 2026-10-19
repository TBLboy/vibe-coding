# Locked Decisions

These decisions are approved for the first V2 implementation. Do not reopen them during routine implementation.

| ID | Decision | Reason |
|---|---|---|
| D-01 | Clean-room rewrite; no old-framework compatibility or migration | Prevent legacy architecture from contaminating the new core |
| D-02 | Four concepts only: Session, Policy, Task, Project Memory | Keep the mental model small |
| D-03 | New Session defaults to balanced | Efficient default for everyday development |
| D-04 | Only explicit `/fast`, `/balanced`, `/strict` commands change mode | No keyword/agent-output mode switching |
| D-05 | No independent reviewer toggle | Review depth is bound to Session/Task policy |
| D-06 | Fast and balanced never invoke reviewer | Avoid review overhead and scope expansion on ordinary tasks |
| D-07 | Strict always creates a Task and requires reviewer `go` after verification | Strict is the explicit high-discipline path |
| D-08 | Task policy is frozen when the Task starts | Session mode changes must not bypass or mutate in-flight rules |
| D-09 | Task creation is conditional in fast/balanced | Do not create tracking artifacts for trivial one-turn work |
| D-10 | Verification is required and risk-proportionate; automated tests are conditional on applicability | Correctness without test ritual |
| D-11 | Project Memory stores durable facts, never action logs | Future usefulness over historical completeness |
| D-12 | `current-session.md` and `progress.md` have distinct purposes and conditional write triggers | Avoid duplicate summaries and unnecessary writes |
| D-13 | Task JSON is the only persistent Task record; review is nested in strict Task | No Run/Evidence/Review record graph |
| D-14 | No Goal runtime, event ledger, SQLite projection, or third-party MCP/plugin bundle | Remove duplicate state and unnecessary dependencies |
| D-15 | Strict review gets at most two automatic repair rounds | Prevent unbounded loops |
| D-16 | No parallel writer orchestration in the first version | Reduce coordination and state complexity |
| D-17 | Reviewer invocation is hard-gated by a one-time permit validated against the active Task JSON | Prevent accidental review in fast/balanced and preserve strict review after a Session mode switch |
| D-18 | Recovery snapshots are per Session; `progress.md` is project-wide | Avoid multiple Sessions overwriting each other’s current-work context |

## Not decided yet (engineering validation, not product ambiguity)

- Exact minimum OpenCode V2 version. Pin after live plugin/permission smoke tests.
- Exact installer implementation. Build only after runtime acceptance; it must preserve unrelated user configuration.
- Whether a later release needs automated cleanup of old plugin-storage mode keys. Not required for core behavior.

These open items do not authorize adding new workflow concepts or external dependencies.
| D-19 | User-approved V2-compatible capability Skills are installed as a managed optional pack and routed by `vibe-main` | Preserve high-value specialist techniques without restoring the legacy lifecycle architecture |
