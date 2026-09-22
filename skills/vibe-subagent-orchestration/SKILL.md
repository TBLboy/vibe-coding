---
name: vibe-subagent-orchestration
description: "Dynamically delegate a Vibe Coding lifecycle role to a bounded Codex subagent, preserve main-agent authority, and integrate structured evidence-backed results."
license: MIT
compatibility: codex
metadata:
  stage: orchestration
  output: subagent-report
---

# Vibe Coding Subagent Orchestration

Use this Skill when a Vibe Coding task has a bounded role that benefits from independent analysis,
parallel work, implementation, or verification.

## Role templates

The global Vibe runtime stores role contracts under:

```bash
VIBE_RUNTIME="${CODEX_HOME:-$HOME/.codex}/vibe-workflow"
ls "$VIBE_RUNTIME/agents"
```

Supported roles:

- `business-analyst`
- `codebase-onboarder`
- `solution-researcher`
- `implementation-builder`
- `verification-reviewer`
- `alignment-reviewer`
- `paper-reader`
- `workflow-distiller`

Build a task-bound prompt with:

```bash
python3 "$VIBE_RUNTIME/scripts/render_subagent_prompt.py" \
  --role <role> \
  --project-root <project-root> \
  --task "<precise delegated outcome>" \
  --scope "<allowed files/modules or read-only boundary>"
```

## Delegation protocol

1. Recover project state and select a role only after identifying its lifecycle purpose.
2. Delegate a narrow, independently reviewable outcome. Do not delegate the entire project.
3. State project root, task, allowed scope, read/write boundary, required evidence, and deadline/stop condition.
4. Use Codex's native subagent facility when available. For multiple agents, parallelize only independent work and use disjoint write scopes.
5. The main agent retains user interaction, C-level decisions, integration, task status, and global-rule authority.
6. If native subagents are unavailable, perform the role serially and label the result `serial-role-fallback`.
7. Do not ask an implementation-builder to self-certify completion. Send completed work to verification-reviewer.

## Routing table

| Trigger | Role | Default boundary |
|---|---|---|
| Business ambiguity or missing rules | `business-analyst` | Read plus business-log drafts; no product code |
| Unknown legacy codebase | `codebase-onboarder` | Read-only |
| Bounded technical decision | `solution-researcher` | Research/read-only |
| Approved task with specification | `implementation-builder` | Explicit disjoint write scope |
| Completed implementation needs evidence | `verification-reviewer` | Read/test only |
| Suspected business/code/test drift | `alignment-reviewer` | Read-only |
| Paper/reproduction request | `paper-reader` | Read/research only |
| Milestone completes or workflow repeats | `workflow-distiller` | Candidate drafts only |

## Required subagent return format

Every delegated role returns:

1. **Confirmed facts and evidence**
2. **Inferences and assumptions**
3. **Artifacts or scoped changes**
4. **Commands/tests and observed results**
5. **Risks, limitations, and unresolved questions**
6. **A concrete recommendation to the Vibe Goal main agent**

The main agent checks the report against the role contract, runs integration/verification as needed,
updates `.project-log`, and never promotes a proposed rule without the proper evidence and authority.
