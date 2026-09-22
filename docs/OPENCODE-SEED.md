# OpenCode Migration Seed

## Purpose

This branch is the OpenCode migration line. It was created from `main` and seeded with the
working tree of the codex implementation at `ad51501`; it does **not** inherit the codex
commit history and does not contain `.project-log`.

The seed commit is intentionally a reference starting point, not the finished OpenCode package.
The following tasks adapt the installed entry points and client-specific surfaces:

- `TASK-070`: OpenCode global rules, agents, commands, and Skills;
- `TASK-071`: OpenCode plugin and hooks integration;
- `TASK-072`: Goal/Loop and subagent orchestration parity;
- `TASK-073`: install, update, uninstall, and release entry points;
- `TASK-074`: format 2/3 cross-client interchange tests;
- `TASK-075`: real OpenCode end-to-end acceptance;
- `TASK-076`: OpenCode documentation and release surface;
- `TASK-077`: independent migration review and GO/NO-GO.

## Seed Boundary

- Source implementation: `codex` branch at `ad51501`.
- Target branch base: `main` at `7fac930`.
- Copied: the codex implementation worktree, including runtime, Skills, tests, and packaging
  assets used as the migration reference.
- Not copied: `.project-log`, codex Git commit history, or codex branch pointers.
- Current README keeps the upstream Codex usage text as reference until `TASK-076` replaces it
  with the final OpenCode documentation.

## Seed Verification

The inherited Python regression suite was run from this branch before the seed commit:

```text
python -m unittest discover -s tests -v
Ran 195 tests in 18.632s
OK (skipped=1)
```

The skipped test is the legacy 0.3.0 archive upgrade test, which requires a source-release
workspace artifact and is unrelated to the OpenCode seed itself.

The package validator was also run during the seed landing:

```text
python runtime/scripts/validate_package.py --root .
Package validation passed.
```
