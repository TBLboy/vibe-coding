# Test and Acceptance Matrix

## A. Pure core tests

Run `npm run test:core`.

### Mode

- `fast`, `balanced`, `strict` are the only valid modes.
- missing/invalid mode normalizes to balanced.
- Mode and active Task keys are Session-scoped; reviewer permits are bound to the project-scoped receipt and exact native call.
- mode command prompt with no task text only requests confirmation.
- mode command prompt with task text preserves the task payload.
- injected policy clearly prohibits reviewer in fast/balanced and requires it in strict.

### Task creation

- strict engineering implementation (even small) and engineering work needing durable tracking require a Task; ordinary consultation without durable tracking needs does not in any mode.
- fast trivial one-turn work does not create a Task.
- fast creates a Task for cross-session recovery, blocker, high risk, durable decision/deliverable, or persistent acceptance criteria.
- balanced creates a Task for non-trivial coordination or any durable persistence signal; file count alone does not decide. The helper is a semantic reference, not a production classifier.

### Task state machine

- strict requires `doneWhen`.
- Task control requires new Task policy to match Session mode, but allows resumed Tasks to retain a different frozen policy.
- only one Task can be registered active per Session.
- a blocked Task can be paused; a completed/cancelled Task can be closed.
- fast/balanced verification pass completes without review.
- strict verification pass enters review, not completed.
- strict cannot complete without `review_go`.
- reviewer authorization is rejected unless the active Task JSON is strict, active, in review phase, verification-passed, and review-pending.
- reviewer authorization is rejected if the Task's persisted policy differs from the frozen policy in the active-Task pointer.
- non-go reviewer verdicts require at least one structured finding.
- verification failure returns to implementation.
- review findings invalidate the previous verification.
- at most two automatic repair rounds are granted; a further finding blocks.
- a user decision requirement blocks immediately.
- terminal states cannot be changed by ordinary transitions.
- blocked Tasks must resume before normal transitions.

### Memory policy

- trivial completed work writes neither current-session nor progress.
- unfinished resumable work writes current-session.
- blocker needing follow-up writes current-session.
- material feature/decision/stage/limitation changes progress.
- ordinary retries/tool operations do not trigger memory writes.

### Workbench sync plugin (single-user worklog sync)

Branch scope (`feat/team-workspace-plugin`): plugin tests and the shared contract tests in `shared/team-contracts/`. The end-to-end test starts the real Workbench from the sibling `team-workspace-workbench` worktree. Server-only tests live on `feat/team-workspace-workbench`.

- `shared/team-contracts/*.test.ts`: stable manifests/hashes, binding validation, change-feed contiguity; `contracts-sync.test.ts` fails when a shared file differs from `SHA256SUMS`.
- `tests/team-device-state.test.ts`: device-private state directory outside the project, binding and Key round trip with validation, disconnect keeps other state.
- `tests/team-scan.test.ts`: sync scope is `AGENTS.md` plus `.vibe/`; `.vibe/.sync/` and temp files excluded; oversized and non-UTF-8 files skipped with a warning without aborting.
- `tests/team-conflicts.test.ts`: device-local conflict store, earliest local content kept on repeated conflicts, deletion conflicts, clear.
- `tests/team-sync-plan.test.ts`: push/pull decision table; unsynced local changes become typed conflicts and are never overwritten.
- `tests/team-mirror.test.ts`: fake HTTP server; first merge, cloud-wins conflict landing, delete propagation, 410 halts automatic sync until forced.
- `tests/team-context-notice.test.ts`: a failure reason is injected once, again only when it changes, cleared silently on recovery.
- `tests/team-periodic-sync.test.ts`: 10s default, override, `0` disables, serialization, failure isolation.
- `tests/task-adopt.test.ts`: `adopt` takes an intact synced Task, voids evidence and review permits; rejects hash mismatch, untracked path, missing manifest, terminal and invalid Tasks.
- `tests/workspace-sync-duties.test.ts`: `vibe-main` route row and sync duties, `a-workspace-connect` Skill never persists the Key, tool surface is exactly five tools.
- `tests/workbench-e2e.test.ts`: real Workbench process and two independent plugin clients; bidirectional sync, conflict and `keep_local` resolution, delete propagation, no Key or admin token in output.

Not covered: host delivery of `execute.after` (end-of-turn debounce) and real OpenCode plugin loading are unverified; Windows has no file-mode or symlink assertions.

## B. OpenCode live smoke tests

These are required before declaring the framework installable; pure core tests do not cover them.

Historical smoke evidence for the pre-repair implementation (2026-10-19; does not validate the P0/P1 changes): in an OpenCode 2.0.29 isolated profile, the local plugin directory loads as `vibe-coding-v2` and `/fast`, `/balanced`, and `/strict` register. In the current provider-backed OpenCode 2.0.32 control layer, a bare `/fast` consumed its one-time token and produced the required confirmation only. A `/strict <task>` smoke completed a persisted strict Task through verification, one-time review authorization, read-only `vibe-reviewer` invocation, reviewer `go`, and Task close. These are targeted compatibility observations, not a general claim for every OpenCode V2 build.

Current local release smoke (2026-11-23) uses the installed OpenCode `v2.3.0`
binary and a temporary installer profile. A real `opencode run --server` startup
loaded the staged `vibe-coding-v2` plugin and emitted command-registration events;
`opencode reload` succeeded and caused a second plugin load. Provider-backed model
execution was attempted but unavailable in this environment (one model returned
no-route and another returned a region `403`), so this is not a model/tool-trace or
live-agent acceptance claim. Eight independently launched client processes against
the real file-backed team server produced one successful mirror sync and seven
fail-closed lock-busy results; the manifest cursor remained valid, no lock/guard
residue or credential leakage was observed. A generated self-signed local HTTPS
endpoint served successfully with private key mode `0600`; this validates local TLS
plumbing only, not production certificates, proxy policy or deployment.

The subsequent automated CA/proxy tests above supersede that stand-alone HTTPS
probe **for the local workbench/plugin transport claim**: certificate validation is
not disabled, system trust is not changed, and actual authenticated sync traffic
crosses TLS. They also extend process coverage from lock contention to real writes
and convergence. They do not change the provider no-route/region403 limitation,
validate a production proxy configuration, or establish Windows ACL compliance.

Provider-backed follow-up: `evaluations/run_provider_host_smoke.py` provides a
bounded **real-model** acceptance, distinct from the earlier failed isolated
profile probes. The current authorized default route (`llmcenter/claude-sonnet-5-5`
on OpenCode2.3.0) successfully executes native `/fast` and `/balanced` plus
`workspace_query_spec`, `workspace_record_progress`, `workspace_status`. It checks
host-owned completed tool traces (including Code Mode nesting), a hidden spec
challenge, server version/local-file hash agreement and observed authoritative
mode/team context. A read-only actual-tool hook additionally verifies progress
returned `synced` and status returned `ok: true` with no error, independently of
the model's Code Mode return formatting.
The fixture uses the current staged plugin and a separate
temporary configuration/database, reusing existing authorization via environment
substitution without changing global configuration. It does not establish all
provider routes or the full strict/negative/restart/compaction release checklist.
Offline harness tests check route-field selection, rejection of unsupported
settings/packages and credential-bearing URLs, and failure of completed status
calls with error payloads. A synthetic subprocess flow exercises aliased key
isolation across discovery/host/installer/client/workbench and SIGTERM cleanup
during the model wait. Do not print raw provider-routing responses.

| Case | Expected result |
|---|---|
| Plugin startup | No plugin/type/API errors |
| New Session | Mode resolves to balanced |
| Task control: start | Rejects policy mismatch and registers one active Task pointer |
| Task control: resume | Restores an active pointer without changing frozen Task policy |
| Task control: pause | Requires a blocked Task and invalidates its pending review permit |
| Task control: close | Requires terminal Task state and valid completion conditions |
| `/fast` | Mode stored as fast; brief acknowledgement only |
| `/balanced` | Mode stored as balanced; brief acknowledgement only |
| `/strict` | Mode stored as strict; brief acknowledgement only |
| `/strict <task>` | Mode changes and task runs in same turn |
| Ordinary prose mentioning `/strict` | Mode unchanged |
| Mode switch during existing Task | Existing Task policy unchanged |
| New Task after mode switch | Uses new Session mode |
| Same Session after compaction/reopen | Selected mode retained |
| Different Session | Does not inherit another Session's mode |
| Fast task completion | Reviewer invocation count = 0 |
| Balanced task completion | Reviewer invocation count = 0 |
| Strict verification pass | Reviewer is invoked |
| Strict reviewer returns go | Task may complete |
| Strict reviewer returns findings | Repair → verification → re-review |
| Third unsuccessful review | Task blocked; no fourth automatic repair |
| Reviewer permissions | Native read and bounded locator work; cannot edit or run native shell/glob/grep |
| Reviewer without permit | Plugin permission hook denies invocation |
| Reviewer with a valid strict review permit | Exactly one invocation is allowed |
| Fast/balanced Task attempts review | Plugin permission hook denies invocation |
| Task blocked during review | Task is paused and pending permit is invalidated |
| Trivial one-turn task | No Task file and no memory write |
| Important milestone | Progress updated once with durable fact, not action log |
| Interrupted non-trivial work | Current session + Task are enough to resume |

The completed `/fast` and strict-review smoke cover their corresponding positive-path rows. All other rows, including `/balanced`, compaction/reopen, policy freezing, cross-Session isolation, and negative reviewer-permission tests, remain required acceptance work.

## C. Release gates

Do not call the package release-ready until:

1. Core tests pass.
2. Plugin commands and storage are verified against the pinned OpenCode V2 build.
3. Agent permissions are verified at runtime.
4. End-to-end fast/balanced/strict cases pass.
5. Fresh install does not overwrite unrelated user configuration.
6. Uninstall/recovery behavior is tested before an installer is distributed.

## V2 capability Skill pack

- Every managed V2 capability Skill has a `SKILL.md` with V2 operating boundaries.
- The main Agent routes every managed capability Skill by an explicit trigger.
- The installer copies Skill files, verifies their digests, and removes only unchanged managed Skill files on uninstall.
- No managed Skill may instruct writes to `.project-log` or create legacy Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects.

## Retired capabilities and upgrade (D-28)

- Exactly 22 managed Skills and matching routes; no active references to the six retired Skill IDs in other Skill instructions, no retired helper/test entrypoints. The old Git archive workflow is not a synchronization or backup substitute.
- Installer upgrade removes unchanged previously managed retired files (including helper scripts); preserves edited or unowned files, former archive settings, unrelated user config and project data. Fresh install does not distribute retired Skills.
- Main Agent default concise/direct/efficient/focused style preserves necessary warnings, evidence and requested detail; no separate communication mode. Online search Skill remains independent from decision research, with source inspection, freshness, cross-checking, untrusted-content and unavailable-tool boundaries. Structural tests only; live model cases remain pending.

## V2 capability Skill routing (`tests/package-shape.test.ts`)

- The routing table declares Chinese aliases as first-class triggers and forbids substituting an improvised parallel flow for a covered capability.
- Every routed Skill carries a Chinese alias in its routing row **and** at the start of its frontmatter `description`, so a request phrased in the user's language reaches the Skill instead of being reinterpreted (regression guard for VIBE-FW-ROUTE-001).

- Prompt refinement: package checks pin exactly one row for each of the 22 Skills and preserve high-impact scope qualifiers (focused online search, trivial edits, routine tests, named branch, explicit Workbench operations, local initialization discovery). The existing sync-duty test still protects the three duties. This is structural evidence only.
- Real-model acceptance: compare old/new Main Agent in identical fresh disposable host sessions with pinned model, mode, fixtures and Skills. Observe simple edits, business constraints, root-cause investigation, design restraint, user corrections, Chinese workflow routing, strict-risk gates and honest blocked delivery. Use actual traces, diffs and checks; do not infer behavioral improvement from prompt size or a green package suite. See the delivery note for the manual A/B protocol.

### UI design routing bundle

- `b-ui-design` is the only discoverable entry. Package checks cover eight relative
  guide routes, resolved active links, text-only assets, project-neutral instructions,
  and complete provenance/normalized SHA-256 for all pinned upstream snapshots,
  licenses and notices. Upstream text is provenance-only, not an executable Skill.
- `scripts/test_vibe_v2_installer.py` checks byte-exact installation of the whole
  bundle, one discoverable entry, and clean removal while retaining user config.
- `skills/b-ui-design/EXAMPLES.md` supplies manual routing oracles for product,
  marketing, reading, critique, interaction, mobile and worst-data scenarios.
  These structural tests are not live model routing trials or proof of UI quality;
  actual designs still need rendered/interaction acceptance in their target project.

## V2 capability Skill completeness

- `b-skill-authoring` structural checks protect domain-value guidance, non-mandatory design dimensions, progressive disclosure with essential safety in the main file, guarded explicit routing, complete Memory contract references, and real-model comparison limitations. Actual authoring quality requires representative positive, near-miss and boundary examples in the real host; a passing package test is not proof of professional gain.

- `tests/package-shape.test.ts` checks managed Skill shape, routing and V2 compatibility. Character count is not a quality gate; domain-specific behavioral acceptance remains separate.
- Core engineering refinement: structural checks guard audit-only authorization, registered-criteria supersession, plan versus registered Task, proportionate specifications, architecture ownership, implementation preservation and independent verification oracles. Existing reference examples must resolve. See the delivery report for eight live positive/boundary scenario pairs; these checks do not execute a model.
- Engineering cognition and knowledge refinement: package checks guard onboarding evidence versus authority, static survey read-only boundaries, explicit source tutoring and actual versus illustrative execution, scenario control boundaries, decision research and paper evidence, brief disclosure and Runtime-owned Task references, and lessons/index plus user-approved AGENTS.md writes. The eight live positive/boundary scenario pairs in the delivery report are manual acceptance, not executed model tests.
- The retained `b-source-code-tutoring/references/teaching-template.md` helper asset is pinned.
- `b-branch-engineering-review` is pinned in the managed list: an explicit-only branch audit whose trigger requires a named branch, with the four-state comparison, capability ledger and evidence grading as its methodology. Its behaviour is validated by the branch scenarios in the design document (deleted-but-contracted code, half-implemented interface, changed default, cross-file contract break, tests without assertions, legitimate deletion, needless abstraction); those scenarios are run by hand against real branches, since a fixture repository for all seven is not shipped.

## Per-work requirement baselines (D-21)

- `tests/package-shape.test.ts` asserts the memory contract defines `.vibe/requirements/<work>.md` plus `README.md` index, that `a-requirement-baseline` maintains the index and the `draft/active/superseded` status, and that no Skill refers to a single shared requirements file.

## Memory root, Task-record validation, reviewer-invocation gate (D-22, D-23)

- `tests/memory-root.test.ts`: nearest-ancestor `.vibe/` wins; fresh project falls back to the start directory; POSIX and Windows roots terminate the walk.
- `tests/task-record.test.ts`: structural schema checks and state-machine invariants (strict needs `doneWhen`, blocked needs `blocker`, cancelled needs `cancelReason`, completed ⇒ `complete`, review phase ⇒ strict + review object, `repairRounds` 0–2).
- `tests/review-authorization.test.ts`: `canCloseTask` rejects a strict Task without an observed reviewer invocation; balanced is unaffected.
- `tests/mode.test.ts`: Session context carries the absolute memory root, recovery path and registered Task.
- `tests/package-shape.test.ts`: plugin wires `resolveMemoryRoot`, `validateTaskRecord`, the review-completion marker and the gated close; sample config uses the real `plugin` key.
- `scripts/test_vibe_v2_installer.py`: config permission bits preserved; backup dir `0700` / files `0600`; stale managed files removed only when unmodified.

## P0/P1 additions

Production adapter simulation tests now drive registered tools and permission/completion hooks, with ownership, policy freeze, stale evidence and reviewer replay regressions. Installer tests use temporary profiles. See `evaluations/README.md` for actual host and L3/L4 model evaluation gates.

### Native background review repair (OpenCode 2.3.0 contract)

`tests/runtime-integration.test.ts` additionally drives real adapter wiring for
`running` launch → child terminal result → natural parent context reconciliation.
It covers pending-before-completion, exact call/child binding, no parent-payload
verdict forwarding, failed/incomplete/malformed/compacted/reused child rejection,
identity rechecks, pause/ownership transfer, plugin reload recovery, stale evidence,
reset/replay rejection, frozen strict policy and the two-repair cap. Existing
synchronous native completion and fast/balanced denial tests remain in place.
These are host simulations; live installed-plugin smoke on the target build
remains a separate gate, not implied by a green local suite.

## P2 — engineering capability evaluation

The existing L1/L2 suite remains unchanged in scope. The installer regression also checks that the three new Skill references are copied byte-for-byte. `evaluations/test_p2_fixtures.py` exercises all six materialized L4 scenarios, fresh Git baselines, the dirty user-edit setup, seeded production bypass and destination rejection. `evaluations/cases.json` contains the six new criteria sets; see `evaluations/README.md` for preparation and independent evaluation. Local fixture checks are not L4 model execution. Real host and model acceptance remain separate release gates.


## Specialist Skill refinement

- Package checks guard the UI routing and scoped accessibility evidence, pinned four-state branch comparisons with a merge **tree** ID, isolation and conflict limitations, binding versus first-sync outcomes, private conflict recovery, admin versus workspace-Key authorization, no blind create retry, and backup/restore approval. Existing UI source pinning, native workspace tests, installer and Workbench HTTP tests remain in force.
- Real-model acceptance remains separate: use comparable rendered UI states, a clean and conflicting branch, offline and remote binding (including failed first sync), and read-only/approved operations in an isolated service. No production actions are implied by this test matrix.


## Project Memory knowledge quality refinement

- Package-shape regression checks guard the installed contract reference, claim-specific authority, selective retrieval, timely canonical maintenance, Session isolation, indexed lessons and user-approved AGENTS.md. They are structural checks, not evidence of model compliance.
- Template v3 retains the exact six files and empty Task/Session state; Workbench tests and local-init tests check content, version, server export equality, installed bytes and refusal to overwrite existing knowledge. The real two-device Workbench test checks identical blank bytes, requirement/lesson/index and recovery transfer and recovery deletion, plus existing import/conflict regression. No sync algorithm or Task schema changes.
- Manual model acceptance: see `evaluations/README.md`, Project Memory section. No real model or cloud test is claimed by the above checks.


## Context efficiency (local structural and host boundaries)

- `tests/mode.test.ts` checks every Session/frozen-policy pair with active and inactive pointers, exact encoded recovery path, deterministic rendering, reviewer exception, and strict gate language. `tests/runtime-integration.test.ts` also switches a live simulated adapter Session from strict to fast, checks both policy scopes, and verifies the existing strict Task can still authorize review. Existing lifecycle/permit/compacted-child rejection tests remain unchanged.
- `tests/package-shape.test.ts` pins the compact footer for all 22 Skills, preserved UI-specific boundary, context/evidence guidance, native compaction recovery and unchanged compaction configuration. The installer continues to distribute current bytes without touching project memory or user model/provider configuration.
- No automated assertion of model intelligence, token savings or provider cost. See the manual context efficiency scenarios in `evaluations/README.md`; use actual target-host usage and comparable successful outputs.

### Mode experience refinement

- `tests/task-policy.test.ts`: ordinary consultation without durable tracking in all modes, durable signals take precedence, clear Fast work vs meaningful Balanced coordination, mandatory Strict engineering work. The helper is a semantic reference, not an automatic production classifier.
- `tests/mode.test.ts`: effective-policy instructions for consultation, risk floor, light Fast, adaptive Balanced and non-ceremonial Strict; switch acknowledgement reflects returned frozen policy without automatic resume.
- `tests/runtime-integration.test.ts`: actual adapter switch feedback with no pointer, same/different policy, active/inactive pointer and another Session; existing Task bytes remain unchanged. Existing Strict-to-Fast permit regression now also checks the tool's user-facing facts.
- `tests/package-shape.test.ts`: structural alignment of product/Agent/Skill instructions, not a claim of model compliance. Real-model mode experience remains a manual release check; see `evaluations/README.md`.

## Independent Reviewer refinement

- `tests/reviewer-search.test.ts`: literal file/text location, artifact inventory, bounds, sensitive/generated/linked/nonregular paths, invalid scopes and no content in results.
- `tests/runtime-integration.test.ts`: production tool registration, consumed permit and host child identity/workspace, denied host permission and pre-read candidate check, later Session allow cannot grant prohibited Reviewer actions in the adapter hook, bound/terminal child and post-review denial, successful multiple-tool child completion. No new verdict or lifecycle state.
- `tests/package-shape.test.ts`: exact default-deny Reviewer grants and professional review contract. These are local adapter and filesystem tests, not actual host authorization or model quality validation. Live evaluation must prove the installed tool can be called, permissions cannot be bypassed, and real material defects are found without preference-based findings.
