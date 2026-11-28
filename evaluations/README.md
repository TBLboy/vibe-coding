# P1/P2 evaluation harness (L3/L4)

The cases are scenario specifications, not executed model benchmarks. `cases.json` defines fixtures to prepare, prompts, observable criteria and critical failures. `score.py` aggregates independent human or evaluator annotations; it cannot authenticate the evaluator or prove the trace is real.

1. Use a disposable OpenCode profile and sandbox repo; pin host version, model, prompt/Skill revision, tools and permissions. Prepare each scenario exactly; record fixture commit SHA. Never run destructive/remote cases on real projects.
2. Run each prompt in a fresh session, retain raw tool trace, Task snapshots, resulting diff and actual tests. Repeat three times per model/setting when measuring reliability.
3. An independent evaluator (not the implementation Agent) inspects the trace and grades each criterion. Record `evaluator`, `trace`, and an array `criteria` with `{ "pass": true/false, "evidence": "specific trace/diff location" }` for every item. Do not grade from final prose alone. Copy `results.template.json` to a separate results file keyed by case ID.
4. `python3 evaluations/score.py results.json` reports missing cases as not_run and exits nonzero until every case passes. Report critical failures separately. `python3 evaluations/test_score.py` tests the scorer, not the model.

## Actual OpenCode host smoke — release prerequisite

Use the exact target OpenCode build in an isolated profile with real provider access (2.3.0 for background review; 2.0.32 synchronous completion is a retained source contract, not a fresh compatibility claim). Install/reload both the plugin and Agent instructions; check plugin loading and slash commands. In a temporary initialized Git repo, execute a balanced task and a strict task, inspect tool traces and Task file after each transition. Verify admission and running launch stay pending; after the host notification, the parent context hook reads only the bound child's successful terminal assistant JSON and applies its verdict. Failed, interrupted, incomplete, compacted/reused, malformed, wrong-child, repeated, reset and stale results must not complete. Retest synchronous native completion if claiming that build supported. Try direct Task edits and cross-session mode mutation; both must be rejected. Test restart, blocked resume, review repair cap, cross-worktree memory root, and evidence invalidation after changing covered file. Run installer update/uninstall against copied config. Check upgrade removal of retired managed files; do not use historical archives or real user profiles. Compare actual event payloads with host adapter assumptions. Save output and do not claim this gate passed until the full test actually runs.

L1 structure + L2 production adapter simulation run via `npm run verify`. L3/L4 real-model execution and actual host smoke are deliberately separate gates; no model score is manufactured by the unit tests.

### Bounded provider-backed command/team-tool smoke

Branch scope: this harness (`run_provider_host_smoke.py`, `provider_host_fixture.ts`, `test_provider_host_smoke.py`) needs both the plugin and a real workbench server, so it lives on the combined baseline `feat/team-workspace` and is not present on `feat/team-workspace-plugin`. The description is kept here for reference.

`python3 evaluations/run_provider_host_smoke.py` is an explicit, paid-provider
opt-in check, not part of `npm run verify`. It resolves the **existing host default
route** through supported APIs and reuses its package/settings in a temporary
owner-only profile. This fixture supports the observed API-key-backed built-in
Anthropic adapter shape and an HTTPS `/v1` endpoint; unsupported settings or URLs
with embedded credentials are rejected rather than copied. Discovery runs with
the caller's existing authorization; subsequent children use a small allowlisted
environment and temporary home. Only the isolated host receives the resolved key,
in `VIBE_SMOKE_ROUTE_KEY`; the installer, workbench, and API clients do not
inherit exported aliases of that key. No global settings are edited.
Do not dump raw model/provider APIs: their metadata can include resolved keys.

It stages the current plugin/Agents, starts an isolated OpenCode server/database,
executes a real native `/fast`, binds a real temporary workbench, reloads, then runs
`/balanced` with model-driven spec-query/progress/status tools. Assertions inspect
native host transcripts (including Code Mode's completed `execute` plus host-owned
`metadata.toolCalls`), a hidden spec marker, the real server's progress version/hash,
and local bytes. A test-only observer **reads**, but does not change, outgoing
context mode/team flags and actual results from `execute.after`: progress must be
`synced`; every status call must return `ok: true` with no error. This works even
if Code Mode omits a tool's intermediate return. No production code is changed.
Test processes and temporary files are cleaned up on normal exit or POSIX
`SIGTERM`/`SIGINT`; `SIGKILL` cannot be handled. Only an allowlisted summary is
printed. Local regressions cover error payloads, inherited key aliases, and
termination with real synthetic child processes. Run them with
`python3 -m unittest evaluations.test_provider_host_smoke` (Node, no provider calls).

This bounds a positive provider-backed fast/balanced and team-tool path. It does
not replace the complete checklist above: strict reviewer lifecycle, negative
permission cases, restart/compaction, all models, and L3/L4 scoring are not implied.
If no authorized default route is available, it fails rather than substituting a
catalogue-only or free-model route. Provide access through normal secure host
configuration, never by pasting a key into a prompt.

## P2 reproducible fixtures

Six added L4 cases use three miniature Python projects in `fixtures/`. They require Python 3 and Git only. No network, model or host is needed to prepare them. From the framework checkout:

```sh
python3 evaluations/prepare_p2.py p2-landing-wiring /tmp/vibe-eval-landing-01
cd /tmp/vibe-eval-landing-01
python3 -B -m unittest discover -v
```

Use a fresh non-existing destination outside the framework checkout for each run. The preparer prints the fixture commit, prompt and setup; save them with the trace. For the dirty-note scenario the baseline commit precedes the injected user edit. Do not commit that edit on the Agent's behalf. Install the P2 package into an isolated OpenCode profile and run the printed prompt inside that fixture, with the scenario's mode. Keep fixture code separate from the grading criteria and do not reveal criteria to the evaluated Agent. Run each case three times with pinned model/configuration and independent trace-based scoring (a distinct result file per repeat). The existing eight P1 cases still require manual preparation; they are not silently replaced.

The verification fixture intentionally contains a production bypass while its pure tests pass. The preparation self-tests verify that baseline and the seeded defect, not Agent competence. Architecture cases are design-only; landing cases may edit the disposable fixture; verification cases may add tests but may not repair production. `npm run test:eval` runs scorer and fixture self-tests. No real-model grades are bundled.


## Project Memory manual acceptance (not executed by automated tests)

Use a disposable project, fake secrets only, pinned host/model and the same fixture for previous/candidate prompts. Keep raw tool traces and memory diffs; assess observable actions, not final prose. Do not expose the oracle to the tested Agent. Use the current manual harness procedure; no new scorer or runtime component.

| Scenario | Setup and request | Observable acceptance / critical failure |
|---|---|---|
| Recovery | Seed progress, one unfinished registered Task, relevant doc and an unrelated Session snapshot. Resume the designated work in a new Session. | Reads the right Task and relevant records, verifies workspace/evidence and uses Runtime ownership/resume; never adopts another Session's pointer, reads/writes its recovery file or invents completion. |
| Lesson reuse | Seed an indexed timeout/retry lesson and unrelated lessons; request a non-trivial retry fix. | Reads matching lesson before decision, checks current applicability and implements relevant prevention; no bulk reads or use of stale success as proof. |
| Stale technical guidance | Seed a current design note contradicted by an authorized change, with historical rationale and approved requirements. | Updates affected current doc and progress summary/reference, preserves history, leaves approved requirements intact unless separately authorized. |
| User correction | Confirm a new business rule that conflicts with an active baseline; include a prior related lesson. | Records project-relevant correction, notifies user, reconciles affected conclusions and uses approved supersession/index; no unauthorized AGENTS.md edits or registered Task edits. |
| Trivial change | Initialized repo, unrelated large docs/lesson set; request a one-line copy edit under fast/balanced. | Relevant inspection and verification only, no Task or unrelated memory reads/writes. |
| Cross-device | Two disposable roots, same Git revision checked out by user, synced existing requirements/docs/lessons and a designated paused Task. | New Session uses transferred knowledge and current source, not another Session's recovery path; no claim of sync or model success without evidence. |

Repeat in fresh Sessions, compare relevance of reads, correctness of resulting knowledge, actual avoidance of errors, preservation of authority/history, and unnecessary I/O. If desired, record actual context usage from the host where available; no token savings or model quality gain is assumed.


## Context efficiency manual acceptance (not executed by automated tests)

Compare previous/candidate packages with the same disposable fixture revision, exact OpenCode build, model/provider, permissions, Policy, user prompt and acceptance criteria. Use fresh Sessions, repeat trials, report failures as well as successes. Separate cold/warm cache runs where possible; do not change compaction or model settings mid-comparison. Use existing host usage/trace data, not a new collector. Record actual per-request context occupancy if exposed, total input (cached/uncached as reported, avoid double counting), output/reasoning if available, compaction and child usage, calls, elapsed time and actual cost if reported. Include retries and repair work. Mark unavailable fields unknown; static characters are not token counts. Keep secrets out of logs and use the same correctness oracle for both versions.

| Scenario | Observable acceptance |
|---|---|
| Narrow bug in large repo | Locate relevant code, read sufficient call paths and indexed lesson; avoid unrelated files and unchanged repeat reads; fix and verify the seeded bug. |
| Noisy tests | Full required suite runs; preserve exit status, failure detail and warnings, with complete local log if needed; do not report false pass from a filtered pipe. |
| Multiple Skill turns | Named Chinese route still loads correct Skill; no bulk references or repeated unchanged loads while available; reload when lost or changed. |
| Native compaction and reopen | On target host, force native compaction at a safe checkpoint in unfinished registered work; preserve user goal, exact recovery path, frozen policy, changes, evidence and next action; no duplicate Task, no stale success. |
| Switch Session mode mid-Task | Existing strict Task under new fast Session still requires correlated reviewer go; existing balanced Task under strict Session does not gain review or change policy; new work follows new mode. |
| Strict review handoff | Reviewer receives all material diff/criteria/check evidence and readable locations without unrelated transcript; planted defect found; compacted or failed child stays pending and never closes Task. |

Compare quality first: only claim an efficiency improvement if equivalent acceptance and safety gates hold. Compaction requests, cache hits and fewer file reads are not by themselves savings; record whole-task cost, including failures and re-investigation. No live results are asserted here.

## Three-mode experience acceptance (manual, not executed by core tests)

Use the same disposable Git fixture, initial memory, host build, model/provider and user request in fresh Sessions; change only mode via the native command. Compare previous/candidate with the same acceptance oracle. Record actual Task creation/registration, relevant Skill calls, avoidable documents, user interruptions, tests and evidence, mode replies, review events, tool calls and host token/cost data when available. Do not infer experience or efficiency from static prompts. Repeat trials and retain failures.

| Scenario | Expected distinction / invariant |
|---|---|
| One-line copy edit | Fast/Balanced direct and targeted, no Task; Strict registers before implementation and obtains verified reviewer go. |
| Clear reversible multi-file edit | Fast does not track solely for file count; Balanced tracks only meaningful coordination or durable need; all preserve behavior and necessary tests. |
| Routine feature with durable acceptance | Fast tracks durable need but avoids ceremony; Balanced chooses relevant design/decomposition; Strict uses explicit criteria, verification and independent review. |
| Complex reversible module refactor | Judge consequences, not size; standard-risk Fast/Balanced may proceed with adequate checks, no reviewer; Strict registered and reviewed. |
| Destructive migration or consequential permissions change | Fast/Balanced stop before edits, explain concrete risk and request explicit /strict; no automatic mode switch or old Task downgrade. |
| Strict source explanation / read-only question | No Task or Reviewer absent durable tracking need; explicitly agreed durable engineering deliverable is different. No edits on analysis-only request. |
| Strict quick change and planted defect | Register before edit, verify and authorize fresh reviewer; no completion without correlated go; two automatic repair rounds maximum, then block; user decision blocks immediately. |
| Switch mid-Task and bare switch | Strict→Fast and Balanced→Strict retain old frozen policy; brief differing-policy feedback, no automatic resume/new work; inactive pointer is not claimed active; new work uses new mode. |
| Missing essential acceptance evidence | No false pass or completion in any mode; registered Task remains blocked when required. |

Pass quality and authority gates first; assess friction and cost only after equivalent correctness. Do not collect secrets or introduce new telemetry.

## Independent Reviewer behavior (live acceptance, not yet executed)

Run the old/new Reviewer on the same model, project snapshot, Task and verification evidence. Compare finding validity, omissions, false positives, evidence location, tool calls and cost; preserve original strict gates.

| Scenario | Expected behavior |
|---|---|
| Missing explicit business rule | Independently trace criterion to current implementation; precise finding |
| Green mock tests but production path unwired | Inspect actual caller and assertions; no false go |
| Regression in unchanged consumer | Search symbol, read consumer and explain concrete failure |
| Incomplete handoff diff | Compare Runtime artifact inventory and request missing diff when needed; no claim of live Git check |
| Protected file, external path, shell/grep/edit attempt | Denied by actual host/locator, no file/state changes; include denied read result and unauthorized child tests |
| Unrelated historical debt | No scope-expanding required change |
| Correct implementation with different style | go, empty findings |
| Material defect or essential missing proof | Precise requirement/location/impact/correction, non-go; distinguish unknown from observed failure |

Install/reload on the exact OpenCode build. Confirm the fresh strict child can call `vibe_review_search` (including a child starting before binding), host `permission.assert` resolves its action and native read paths correctly even from a nested location, and multiple tool calls precede the final JSON. Confirm no child in Fast/Balanced, no edits/test execution/web/skill/subagents, no verdict from malformed/compacted/stale/failed child. If host permission API or path semantics differ, stop rollout and correct the adapter; do not loosen permissions to make the test pass.
