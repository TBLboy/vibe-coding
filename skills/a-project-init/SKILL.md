---
name: a-project-init
description: "Initialize a new project with the minimal V2 rules and memory layout."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# V2 Project Initialization

Use when the user asks to initialize, set up, or bootstrap a project ("初始化项目 / 初始化这个项目").

## Output

Root `AGENTS.md` with two parts, plus `.vibe/progress.md`, the `.vibe/docs/` directory, and the current Session's recovery file:

- **通用开发规则**: injected verbatim from `templates/general-rules.md` inside the managed markers `<!-- VIBE-PROJECT-GENERAL:BEGIN -->` … `<!-- VIBE-PROJECT-GENERAL:END -->`. The template is the single source of these rules; never retype or summarize them.
- **项目级规则**: distilled by you from the project's real facts. Never invented.

Create the current Session's `.vibe/sessions/<url-encoded-session-id>/current-session.md` (initialization is the start of work; the file records that and the next action). Do not create `.vibe/tasks/` or `.vibe/requirements/`; V2 creates those only when real work warrants them.

## Workflow

1. Confirm the project root (the current working directory unless the user names another).
2. Determine the repository type when it matters for rule 7: inspect `git remote -v`; if the project is a Git repository and the type (个人仓库 / 团队协作仓库) cannot be inferred, ask the user once. If the directory is not a Git repository, do not run `git init` unless the user asks.
3. Read the project's `README*`, `docs/`, top-level build/dependency files (`pyproject.toml`, `package.json`, `Makefile`, `CMakeLists.txt`, …), and test layout. Distill **project-level rules**: architecture boundaries, module conventions, how to build/run/test, hardware or safety constraints, team conventions. Include only facts confirmed in the project; if nothing usable exists, leave the rules empty and say so.
4. Run the deterministic script (installed with this Skill):

   ```bash
   python3 "${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/skills/a-project-init/scripts/init_project_v2.py" \
     --target <project-root> \
     --session-id <current-session-id> \
     [--project-rules "<distilled project rules>"] \
     [--repo-type personal|team]
   ```

   `--session-id` is the raw OpenCode Session ID of this Session: take it from the `Session recovery file:` path the plugin injects into your context (the segment under `.vibe/sessions/`, URL-decoded; IDs look like `ses_…`). Never invent one or reuse another Session's.
5. Read the resulting `AGENTS.md` and report: the `AGENTS.md` status (`created` / `injected` / `updated` / `unchanged` / `markers-unbalanced` / `markers-ambiguous`), the `progress.md`, `docs/` and session-file status, the repository type, and whether project rules were provided or left empty.

## AGENTS.md update semantics

- No `AGENTS.md`: create it — managed general block first, then `## 项目级规则`.
- Existing `AGENTS.md` without markers: keep every existing byte (treated as project-level content) and inject the general block at the top; a `## 项目级规则` section is appended only when you pass rules or a repo type and the heading does not already exist.
- Existing markers: only the span between the markers is replaced; `unchanged` when already identical. Re-running after editing `templates/general-rules.md` is how general rules propagate to projects.
- `markers-unbalanced` / `markers-ambiguous`: the file is left untouched; ask the user to fix the marker layout.
- `.vibe/progress.md` is created from `templates/progress.md` only when missing.
- The Session recovery file is created from `templates/current-session.md` only when missing; it follows the normal rule afterwards (delete once nothing resumable remains).
- `.vibe/docs/` is created (with a `.gitkeep`) only when missing. It is the home for the project's miscellaneous documents — specs, research notes, briefs, meeting notes — that are not rules, progress, baselines, or Task state.

## Maintenance

- To change a general rule, edit `templates/general-rules.md` in the framework and re-run initialization; do not edit each project's managed block by hand.
- Project-level rules live outside the markers and are owned by the project.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
