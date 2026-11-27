---
name: a-workspace-connect
description: "连接工作空间/绑定 Key/连接 Workbench/接入云端日志 | Bind the project root to a Workbench workspace from a workspace Key and start automatic two-way sync of AGENTS.md and .vibe/."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Workspace Connect

Use when the user hands over a workspace Key and asks to connect this project to a Workbench workspace (「用这个 key 连接 workbench」「接入云端日志」). Connecting is a one-step action: no extra confirmation, no manual pull or restore afterwards.

## What connecting means

- One workspace has one Key. The Key alone decides which cloud workspace the local project binds to; the local directory name is irrelevant, so two machines with different folder names reach the same workspace with the same Key.
- The bound root is the project memory root injected by the plugin (the directory that owns `.vibe/`, or the Session directory for a fresh project), never a Git sub-repository inside it. All sub-repositories share the root's `AGENTS.md` and `.vibe/`.
- After binding, the plugin syncs `AGENTS.md` and the whole `.vibe/` with the cloud every 10 seconds while OpenCode runs. The cloud copy is the single authoritative project log.
- This Skill never creates `AGENTS.md` or `.vibe/` locally. Creation belongs to Workbench; an empty local root receives both from the first sync. There is no local initialization path in this framework.

## Flow

1. Take the Key from the user's message. Do not write it into any file, Task, progress note or memory, and do not repeat it back in replies.
   - A brand-new project has no local `AGENTS.md` or `.vibe/` and may not have a Key yet. In that case ask for an existing Key, or create a workspace first through `b-workbench-remote-ops` (administrator Token) and use the returned Key. Never run a local project initialization to produce those files.
2. Call `workspace_status`.
   - Not bound: continue.
   - Already bound to the workspace this Key belongs to: report that it is already connected and show the sync state; stop.
   - Bound to a different workspace: tell the user which workspace (name and type) this root is bound to, and ask whether to disconnect it first. Only after a yes, call `workspace_disconnect`, then continue. Never rebind silently.
3. Call `workspace_connect` with `key`. The server address is a machine-level setting (`WORKBENCH_URL`) read by the plugin. Only when the plugin reports it missing, ask the user for the address once and pass it as `serverUrl`.
4. On success the plugin stores the binding, the Key and the sync state in the device-private directory outside `.vibe/`, records the workspace type, and runs the first sync immediately.
5. Read the result and report in a few lines: workspace name and type, number of files downloaded, number uploaded, and number of conflicts.

## First-sync merge (performed by the plugin, reported by you)

- Same path, same content: already in sync.
- Only local: uploaded. Only in the cloud: downloaded.
- Same path, different content: the cloud version lands at the path, the local content goes to the device-local conflict store outside `.vibe/`, and the conflict is listed for the user. Do not choose a side; hand the decision to the conflict flow (`workspace_resolve_conflict`) once the user decides.
- Files that are not UTF-8 text, exceed 1 MiB, or are temporary files are skipped with a warning. They are not conflicts.

## Failure handling

- Key rejected or unknown: say so plainly; ask the user to re-check the Key (it is shown only once, when the workspace is created). Do not retry with variations.
- Workspace archived: the Key is no longer valid; nothing is bound.
- Server unreachable: report it, keep local files untouched, and note that the plugin retries by itself with backoff once the connection returns. Binding succeeds only after the server has accepted the Key.
- Never delete or overwrite local files to make a connection succeed.

## Boundaries

- Reconnecting with the same Key after `workspace_disconnect` follows the first-sync merge again.
- `workspace_disconnect` only removes this machine's binding; local files stay.
- Sync status questions after connecting use `workspace_status`; do not poll it.

## V2 operating rules

- For registered Tasks, use Runtime lifecycle events in `docs/03-STATE-MACHINE.md`; never edit Task JSON directly.

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
