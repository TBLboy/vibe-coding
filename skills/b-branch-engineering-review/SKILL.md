---
name: b-branch-engineering-review
description: "分支审查/工程审查/审查这个分支/合并前审查 | Review one repository branch as an engineering change against its target branch using four-state comparison, a capability and contract ledger, and an evidence-graded report. Trigger only on an explicit request to review a named branch; never infer this review from ordinary code reading."
license: MIT
compatibility: opencode
metadata:
  v2: true
  routing: automatic-narrow
---

# Branch Engineering Review

## Purpose

Review a topic branch (feat, fix, refactor, chore — any branch) from the standpoint of the maintainer who owns the target branch.

- Ordinary code review: is this code correct?
- Feature review: is this feature well implemented?
- Branch engineering review: **how will this change alter the system I maintain?**

Report what changed, what was preserved, what was lost, which contracts moved, and which engineering decisions the developer made on the maintainer's behalf. The user keeps the decision. Never return a merge verdict or an overall score.

No text conflict, a runnable feature, and green tests do not make a change engineering-sound.

## Trigger and input contract

Start only when the user explicitly asks to review a named branch. Reading code, explaining a diff, or a passing mention of a branch is not a trigger.

Inputs:

- `F` — the branch under review, as named by the user.
- `T` — the target branch. Use the user's value; when the user gave none, use the current branch and print one line: `目标分支：<T>（默认取当前分支）`.

Fail fast, one line, then stop. Do not search for similar names, `git log --all` for a rename, or suggest alternatives:

- `F` (or `T`) does not exist in the repository → report that the branch does not exist.
- The directory is not a Git work tree → report it.
- `F == T` → report that they are the same branch.

## Four-state comparison

Do not review the diff alone. Establish four states and record their commits:

```text
             B: merge base
              /         \
    T: target            F: feature
              \         /
             M: simulated merge
```

| Comparison | Question |
|---|---|
| B → F | What did the feature branch itself develop, and with what intent? |
| B → T | How did the target branch evolve in the same period? |
| T → M | What will the maintainer actually receive? |
| F → M | Does the feature's intended behavior still hold after integration? |

Resolve named refs to immutable commit IDs first (`git rev-parse --verify` on
exact branch refs); use these IDs throughout, not moving branch names. Run
`git merge-base --all T F`: record all bases if multiple; do not pretend one
arbitrary base is the exact merge algorithm's virtual base. No common history
means integration is unverified; do not force unrelated histories.

Build `M` only in a fresh isolated detached worktree at the pinned target SHA,
never in the user's working tree, never committing to or pushing either branch.
Inspect local hooks, filters, merge drivers and test commands before executing;
if untrusted execution cannot be excluded or authorized, limit to static evidence.
Use a unique temporary directory and a merge with `--no-commit --no-ff` and the
pinned feature SHA. Disable hooks for the isolated commands; do not alter global
or repository configuration. On a clean result, `git write-tree` records the
merged index tree ID; `HEAD` still denotes T, not M. Compare T and F against this
actual tree. Record `base_sha` (or bases), `target_sha`, `feature_sha`, and
`merge_result_tree` (or `unbuilt`), not a fabricated merge commit SHA.

If conflicts occur, record paths, index stages and both sides; `M` is unbuilt.
Continue static comparisons and identify what integration remains unknown. Do not
use `-X ours` as evidence of the actual merge, or resolve conflicts for the user.
Remove only the review-created worktree, even on failure; do not prune unrelated
worktrees. If cleanup fails report the exact residual location. Never modify the
user's worktree, refs or index. Running branch code/tests needs a safe isolated
environment without production credentials or data; read-only review does not
authorize deployment or external effects.

Zero file overlap is not proof of semantic agreement. Track shared interfaces, configuration keys, dependency versions, generated artifacts, and shared state across files.

## Target-branch baseline

You cannot judge a change to a system you have not read. Reconstruct the target branch before evaluating the feature:

- module boundaries and dependency direction;
- the core execution path the change touches;
- public interfaces, configuration, and default values;
- error handling, lifecycle, and resource ownership;
- test conventions;
- design decisions recorded in docs, ADRs, or commit history.

Separate explicit constraints, current behavior, and inferred intent. Do not treat every detail of the current implementation as an unchangeable contract, and do not treat an unfamiliar historical design as redundancy.

When the repository is unfamiliar and no prior baseline exists, build only the minimum needed for this review — do not run a full codebase onboarding as a side effect.

## Forward and backward review

Run these as two independent passes. Do not let the feature's own narrative decide what is worth looking at.

**Forward (Addition).** Architecture fit, interface completeness, functional closure, code quality, safety, and the test evidence for the new behavior. Check for placeholders, empty implementations, unreachable code, and features not wired into a call chain.

**Backward (Preservation).** Start from the old capability, not from the diff: for each affected behavior, find its original implementation, its replacement, every caller, and the evidence that behavior is equivalent. Deletions, replacements, default-value changes, contract narrowing, and silent fallbacks belong here.

## Capability and contract ledger

Analyze in units of engineering capability and contract, not files or lines. Status per row: added, preserved, modified, replaced, removed, unknown.

For every removed or replaced capability, state where the responsibility went, why, which callers are affected, and what proves behavioral equivalence. For every interface, check all implementations, registrations, instantiation points, configuration entry points, and real call chains.

No TODO/FIXME does not mean complete; no dangling reference does not mean the deletion was sound.

## Engineering decision inventory

Record decisions the developer made that belong to the maintainer: background, previous approach, new approach, stated rationale, alternatives, impact, and open questions. When the rationale was never recorded, mark it unknown — never invent a motive.

These are not automatically defects. They must be visible, not absorbed as implementation detail.

## Necessity, independence, reversibility

Judge whether this scope of change was required, whether a smaller change achieves the same outcome, and whether the parts can be verified, merged, or reverted separately. Reference expand → migrate → contract, but do not demand that every change be split, and do not oppose deletion or refactoring on principle.

## Evidence discipline

| State | Meaning |
|---|---|
| Confirmed | Direct source, configuration, or history evidence |
| Verified | Actually executed, with the scope recorded |
| Inferred | Reasoned from evidence, not directly checked |
| Unverified | Identified as needing verification, no evidence yet |
| Unknown | Missing information; cannot judge |

Evidence state is independent of severity. Never upgrade these facts into stronger claims:

- no file overlap → no semantic conflict;
- many new tests → adequate testing;
- compatibility code present → fully backward compatible;
- no TODO/FIXME → feature complete;
- nothing found → nothing wrong.

Every finding carries a locatable file plus line or symbol and the commit it came from, the fact, the inference, the impact, and how to verify it. Record the exact commands, environment, and results actually run, and why anything was not run. Never fabricate a result.

## Scale

For a large branch, review in batches by logical change and affected subsystem, then do a cross-module pass. State the covered range and the uncovered parts. Sampling is not full coverage.

Declare the report depth at the top and why: a small fix branch and a large feature branch do not get the same report.

## Report

Write the review report to the user-chosen path, or default to a safe filename
under the project root such as
`branch-review-<target>-<feature>-<short-sha>.md`; sanitize branch names to single
filename components and never overwrite an existing report without approval.
It is a review artifact, not project memory — do not place it under `.vibe/`.

Use relevant sections at the chosen depth: scope and baseline; change landscape; architecture before and after; capability and contract ledger; engineering problems; engineering decisions; integration and impact; tests and evidence; benefit and cost; open decisions.

Finding template:

```markdown
### [BR-NNN] Title
- Type: defect / design issue / contract change / technical debt / risk to verify
- Severity: Critical / High / Medium / Low / Informational
- Evidence: Confirmed / Verified / Inferred / Unverified / Unknown
- Location: branch or commit + file + line or symbol
- Fact: the concrete difference between old and new behavior
- Analysis: why it matters, which constraint it violates
- Trigger and reach: callers, scenarios, modules, runtime environment
- Verification: source, test, or experiment, with its limits
- Suggestion and open questions: options, what the developer must explain, what the maintainer must decide
```

Severity follows real impact, trigger conditions, and recovery cost — not diff size. `Informational` records a material change that is not a defect. Do not dress an engineering decision up as a bug. Record sound engineering improvements and justified deletions as evidence, not only the negative findings.

## Completion gate

The review is complete when all of these hold:

- the pinned states and merged tree are recorded, or the missing state is named as a limitation;
- every capability within the reviewed scope appears in the ledger with a status;
- every finding carries a location and an evidence state; unresolved high-impact unknowns are explicit;
- the isolation worktree is removed;
- the report states what was not reviewed.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
