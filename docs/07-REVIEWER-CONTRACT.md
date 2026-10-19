# Strict Reviewer Contract

## Purpose

The reviewer is an independent, read-only validation phase used only by strict Tasks. It is not a product designer, refactoring agent, or second implementation pass.

## Required input

- Task `goal` and `doneWhen`;
- explicit user constraints and relevant project `AGENTS.md` rules;
- changed diff/files and only the surrounding code needed to understand them;
- current verification result and known limitations.

The reviewer should not receive a transcript of every action, all shell output, unrelated files, or model reasoning. The main Agent supplies the relevant diff and verification summary; the reviewer has no shell or edit access.

## Questions to answer

1. Does the change satisfy each applicable `doneWhen` criterion?
2. Is there an observable defect or regression in the agreed scope?
3. Does the change violate an explicit business rule, interface contract, security constraint, or project rule?
4. Is the supplied verification sufficient for the actual change and risk?

## Verdicts

- `go`: acceptance criteria are satisfied; no material in-scope defect remains.
- `conditional`: specific, objectively fixable requirements remain unmet.
- `no-go`: a material requirement is unmet, a critical defect exists, or a product/business decision is required.

## Finding format

Every finding is a structured object with `severity`, `requirement`, `location`, `problem`, and `requiredChange`. Use severity `critical`, `major`, or `minor`; identify the exact requirement/constraint, a file/line or precise symbol, the observable problem and impact, and the smallest required change.

Do not report style preferences, speculative concerns without a concrete failure path, optional improvements, unrelated debt, or feature ideas as blockers.

## Authority and restrictions

- Reviewer does not edit product code.
- Main Agent owns fixes, verification, and re-review.
- Reviewer may not expand scope or rewrite acceptance criteria.
- A review verdict is not a substitute for verification.
- Only `go` permits strict Task completion.
- Two automatic repair rounds are the maximum. A third unsuccessful review blocks the Task; report the unresolved findings and do not retry automatically. Any further attempt requires a new explicit user request.
