# P1/P2 evaluation harness (L3/L4)

The cases are scenario specifications, not executed model benchmarks. `cases.json` defines fixtures to prepare, prompts, observable criteria and critical failures. `score.py` aggregates independent human or evaluator annotations; it cannot authenticate the evaluator or prove the trace is real.

1. Use a disposable OpenCode profile and sandbox repo; pin host version, model, prompt/Skill revision, tools and permissions. Prepare each scenario exactly; record fixture commit SHA. Never run destructive/remote cases on real projects.
2. Run each prompt in a fresh session, retain raw tool trace, Task snapshots, resulting diff and actual tests. Repeat three times per model/setting when measuring reliability.
3. An independent evaluator (not the implementation Agent) inspects the trace and grades each criterion. Record `evaluator`, `trace`, and an array `criteria` with `{ "pass": true/false, "evidence": "specific trace/diff location" }` for every item. Do not grade from final prose alone. Copy `results.template.json` to a separate results file keyed by case ID.
4. `python3 evaluations/score.py results.json` reports missing cases as not_run and exits nonzero until every case passes. Report critical failures separately. `python3 evaluations/test_score.py` tests the scorer, not the model.

## Actual OpenCode host smoke — release prerequisite

Use the exact target OpenCode build in an isolated profile with real provider access (2.3.0 for background review; 2.0.32 synchronous completion is a retained source contract, not a fresh compatibility claim). Install/reload both the plugin and Agent instructions; check plugin loading and slash commands. In a temporary initialized Git repo, execute a balanced task and a strict task, inspect tool traces and Task file after each transition. Verify admission and running launch stay pending; after the host notification, the parent context hook reads only the bound child's successful terminal assistant JSON and applies its verdict. Failed, interrupted, incomplete, compacted/reused, malformed, wrong-child, repeated, reset and stale results must not complete. Retest synchronous native completion if claiming that build supported. Try direct Task edits and cross-session mode mutation; both must be rejected. Test restart, blocked resume, review repair cap, cross-worktree memory root, and evidence invalidation after changing covered file. Run installer update/uninstall against copied config. Run archive push only against an isolated local bare remote. Compare actual event payloads with host adapter assumptions. Save output and do not claim this gate passed until the full test actually runs.

L1 structure + L2 production adapter simulation run via `npm run verify`. L3/L4 real-model execution and actual host smoke are deliberately separate gates; no model score is manufactured by the unit tests.

## P2 reproducible fixtures

Six added L4 cases use three miniature Python projects in `fixtures/`. They require Python 3 and Git only. No network, model or host is needed to prepare them. From the framework checkout:

```sh
python3 evaluations/prepare_p2.py p2-landing-wiring /tmp/vibe-eval-landing-01
cd /tmp/vibe-eval-landing-01
python3 -B -m unittest discover -v
```

Use a fresh non-existing destination outside the framework checkout for each run. The preparer prints the fixture commit, prompt and setup; save them with the trace. For the dirty-note scenario the baseline commit precedes the injected user edit. Do not commit that edit on the Agent's behalf. Install the P2 package into an isolated OpenCode profile and run the printed prompt inside that fixture, with the scenario's mode. Keep fixture code separate from the grading criteria and do not reveal criteria to the evaluated Agent. Run each case three times with pinned model/configuration and independent trace-based scoring (a distinct result file per repeat). The existing eight P1 cases still require manual preparation; they are not silently replaced.

The verification fixture intentionally contains a production bypass while its pure tests pass. The preparation self-tests verify that baseline and the seeded defect, not Agent competence. Architecture cases are design-only; landing cases may edit the disposable fixture; verification cases may add tests but may not repair production. `npm run test:eval` runs scorer and fixture self-tests. No real-model grades are bundled.
