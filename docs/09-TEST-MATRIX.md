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

- strict always creates a Task.
- fast trivial one-turn work does not create a Task.
- fast creates a Task for cross-session recovery, blocker, high risk, durable decision/deliverable, or persistent acceptance criteria.
- balanced creates a Task for multi-step/multi-file work or any durable persistence signal.

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

## B. OpenCode live smoke tests

These are required before declaring the framework installable; pure core tests do not cover them.

Historical smoke evidence for the pre-repair implementation (2026-10-19; does not validate the P0/P1 changes): in an OpenCode 2.0.29 isolated profile, the local plugin directory loads as `vibe-coding-v2` and `/fast`, `/balanced`, and `/strict` register. In the current provider-backed OpenCode 2.0.32 control layer, a bare `/fast` consumed its one-time token and produced the required confirmation only. A `/strict <task>` smoke completed a persisted strict Task through verification, one-time review authorization, read-only `vibe-reviewer` invocation, reviewer `go`, and Task close. These are targeted compatibility observations, not a general claim for every OpenCode V2 build.

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
| Reviewer permissions | Cannot edit; cannot run arbitrary shell, glob, or grep |
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
- No migrated Skill may instruct writes to `.project-log` or create legacy Goal, Run, ledger, SQLite, standalone Evidence, or reviewer transcript objects. `a-project-archive` may *name* the pre-existing V1 snapshots inside the archive repository so it can forbid touching them; a mention that frames creating or writing them fails the test.

## V2 project archive

- Archive snapshots contain only project-root `AGENTS.md` when present and `.vibe/` memory.
- Archive publication validates SHA-256 manifest entries, never modifies source files, and rejects unsafe paths.
- The archive root is remembered in the installed Skill (`archive_root.conf`, user data, never shipped or deleted by the installer): unconfigured → exit 3 and ask once; `--set-archive-root` validates an existing absolute directory and persists it; later runs reuse it.
- Archiving publishes: the snapshot directory is committed and pushed to the archive repository's branch, and the remote ref is confirmed equal to the local commit; an unrelated file in that repository is never committed.
- A snapshot directory matched by the archive repository's `.gitignore` raises instead of producing an empty, unpublished commit.
- A snapshot that cannot be published is reported, not silently accepted: a plain directory and a remote-less repository both return `publish.status` `not-a-repository` / `no-remote`, and the command exits 4 with "NOT pushed"; `--no-push` returns `skipped` and exit 0.

## V2 project initialization (`scripts/test_v2_project_init.py`)

- A fresh project receives the full managed general-rules block from `templates/general-rules.md`, a `## 项目级规则` section (distilled rules or an explicit empty hint), , `.vibe/progress.md`, `.vibe/docs/` and — given `--session-id` — the URL-encoded current Session recovery file; `.vibe/tasks/` is never pre-created.
- An existing `AGENTS.md` keeps every byte (including CRLF); the managed block is injected at the top, and a rerun is `unchanged`.
- A template change updates only the span between the markers; malformed markers are reported and the file is left untouched.
- The general rules lead with the end-of-reply 点拨 (mentoring) rule as rule 1 — name the engineering term / pattern / mental model behind the user's informal question or action in 1–3 sentences, or stay silent when nothing is worth naming — and the remaining rules are numbered contiguously after it.

## V2 capability Skill routing (`tests/package-shape.test.ts`)

- The routing table declares Chinese aliases as first-class triggers and forbids substituting an improvised parallel flow for a covered capability.
- Every routed Skill carries a Chinese alias in its routing row **and** at the start of its frontmatter `description`, so a request phrased in the user's language reaches the Skill instead of being reinterpreted (regression guard for VIBE-FW-ROUTE-001).

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

- `tests/package-shape.test.ts` requires every managed Skill to carry at least two methodology sections beyond the shared V2 operating rules and a minimum length, so a Skill cannot regress to a summary stub.
- Restored helper assets are pinned: `b-opencode-model-config/scripts/configure_models.py` (`scripts/test_v2_configure_models.py`: defaults applied, legacy `attachment` removed, unrelated keys and file mode preserved, dry-run writes nothing, idempotent, unknown provider/model rejected) and `b-source-code-tutoring/references/teaching-template.md`.
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
- `scripts/test_v2_project_init.py`: nested `.vibe/` refused unless `--allow-nested`.

## P0/P1 additions

Production adapter simulation tests now drive registered tools and permission/completion hooks, with ownership, policy freeze, stale evidence and reviewer replay regressions. Installer/archive tests use temporary profiles and local Git remotes. See `evaluations/README.md` for actual host and L3/L4 model evaluation gates.

## P2 — engineering capability evaluation

The existing L1/L2 suite remains unchanged in scope. The installer regression also checks that the three new Skill references are copied byte-for-byte. `evaluations/test_p2_fixtures.py` exercises all six materialized L4 scenarios, fresh Git baselines, the dirty user-edit setup, seeded production bypass and destination rejection. `evaluations/cases.json` contains the six new criteria sets; see `evaluations/README.md` for preparation and independent evaluation. Local fixture checks are not L4 model execution. Real host and model acceptance remain separate release gates.
