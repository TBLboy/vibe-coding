# Project Log v2 Reference

## File ownership

| File | Primary writer | Notes |
|---|---|---|
| workflow.yaml | vibe-goal | Phase changes require gate evidence |
| business-logic/atoms.yaml | business-clarify / vibe-goal | Active semantics cannot be changed from code alone |
| requirements/baseline.yaml | requirement-baseline | Versioned; supersede rather than overwrite history |
| tasks/task-list.yaml | vibe-goal / task-decompose | Every status change should preserve verification integrity |
| decisions/decision-log.yaml | any decision-making Skill | B and C decisions should be recorded |
| research/solution-research.yaml | solution-researcher | Evidence date and conditions required |
| architecture/architecture.yaml | architecture-decision | Reference supporting business atoms and decisions |
| specs/* | engineering-spec | One spec per non-trivial task or coherent group |
| alignment/findings.yaml | vibe-goal after read-only audit | Reviewer returns draft; primary decides repair/escalation |
| retrospective/retrospective.yaml | retrospective | Evidence-backed improvement only |
| distillation/candidates.yaml | operator-distill | Staged promotion; never silently update global assets |
| current-session.md | vibe-goal | Concise, current, resumable |

## Fact priority

1. current user-confirmed decisions;
2. active requirement baseline;
3. active business atoms;
4. active decisions;
5. acceptance evidence;
6. code/config;
7. inference.

## Safe update patterns

- append new IDs; do not reuse IDs;
- supersede records instead of mutating history invisibly;
- use `draft`, `experimental`, or `conflict` when certainty is insufficient;
- write paths relative to the project root;
- preserve evidence and limitations;
- after edits run the validator.

## Large project scaling

When a single YAML file becomes difficult to maintain, split by domain while retaining an index file. Do not split prematurely. The validator can later be extended to resolve domain indexes.
