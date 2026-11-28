---
name: a-workspace-connect
description: "初始化项目/本地初始化/离线初始化/连接工作空间/绑定 Key/连接 Workbench/接入云端日志 | Bootstrap via Workbench creation and Key binding (default), connect an existing workspace for automatic two-way log sync, or explicitly initialize locally/offline."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Workspace Connect

## Intent and ownership

Initialize or attach the resolved project memory root to Workbench. Workbench
creation + Key binding is the default; explicit local/offline initialization is
independent. A Key selects the workspace, not the directory name. Use the
plugin-injected memory root (nearest owner of `.vibe/`, or Session directory for
a fresh project), not a nested Git repository. Git source synchronization remains
the user's responsibility. Only AGENTS.md and eligible `.vibe/` files sync;
Workbench is the authoritative shared log, not an independent historical backup.

Loading this Skill is not consent to create, import, rebind or resolve conflicts.
An explicit connect request with a Key authorizes connecting to that workspace,
not changing an existing binding. Do not write it into any file yourself or echo the Key in replies, Task, memory,
shell arguments or logs; only the connector owns private credential storage. Use the native workspace tools when available.

## Choose the path

- **Local/offline:** only when explicitly selected. Resolve root and supported
  type (`engineering-dev` currently). Run the installed
  `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/runtime/opencode/plugins/vibe-v2/team/init-local.ts`
  with Node `--experimental-strip-types` and arguments `root engineering-dev`.
  It uses the canonical distributed six-file template without network or Key,
  rejects an existing root/ancestor memory or binding, and never overwrites logs
  or creates fake Session/Task state. Report actual output and residual paths if
  rollback fails; stop. Do not fall back to remote creation.
- **Remote, no Key yet:** ask for an existing Key or obtain explicit authorization
  to create via `b-workbench-remote-ops` (blank template or import existing logs).
  Creation and import are server operations, not local initialization. Never
  overwrite existing logs or silently create blank instead of importing.
- **Remote, Key supplied:** use the binding flow below; no redundant confirmation
  for the explicitly requested first connection.

## Bind and check actual results

1. Call `workspace_status` if available (`not_bound` or `bound:false` is unbound).
   It reports the current workspace ID/type and sync status, not the identity of
   a newly supplied Key. Never infer that two Keys reach the same workspace.
2. Call `workspace_connect` with `key`; use configured `WORKBENCH_URL` (or existing
   binding URL) and supply `serverUrl` only if needed. Use a verified HTTPS URL
   for public networks, never bypass certificate validation. For a missing URL,
   ask once. If the tool returns `bound_to_other`, show current identity/type
   and obtain permission to disconnect; only then call `workspace_disconnect`
   and reconnect. Do not disconnect based on an unverified Key.
3. Distinguish `connected`, `already_connected` and `bound_to_other` from the
   returned `sync.ok`, `lastError`, `halted`, `warnings`, `conflicts` and `pending`.
   Binding success does not prove first sync success. Report only available
   facts, including warnings/conflicts; no fabricated transfer counts.
4. If native tools are unavailable, run the installed sibling `connect.ts` with
   the resolved root and credentials from `WORKBENCH_URL`/`WORKBENCH_KEY` in the
   process environment, not command-line arguments. It binds only; report
   `/reload` to load automatic sync, then verify status once when requested.
   Do not claim the CLI performed first sync. If it refuses an existing binding,
   use native tools after reload or report the limitation, not private-state edits.

## Synchronization and conflicts

Automatic sync runs while OpenCode runs (normally every 10 seconds); use
`workspace_status` for status and `workspace_sync` only as an explicit or
necessary immediate fallback, not polling. Initial reconciliation for eligible
files: equal content is already in sync; local-only uploads, remote-only downloads;
different content at the same path preserves the local version privately and
applies remote. Unsafe, oversized, non-UTF-8 paths may be skipped with warnings;
`.vibe/.sync` and `.tmp-` entries are excluded. Skipping is not deletion or conflict.

Use `workspace_resolve_conflict` only with the user's decision and exact path:
`keep_remote`, `keep_local`, `merged` (requires content), `accept_delete`, or
`keep_modified` as appropriate. `keep_local`/`keep_modified` uses the saved main
conflict copy, not necessarily the latest local edit. Subsequent distinct local
contents can be in device-private recoveries; keep them private and do not delete
them automatically. If result is `cloud_changed`, present the refreshed state
and obtain a new decision; do not blindly repeat the previous resolution.

## Failure and recovery

Rejected/unknown Key or archived workspace: report the actual error and ask the
user to verify credentials; do not guess, rotate or retry blindly. An initial
failed bind is distinct from a failed sync after binding. Existing sync retries
transient failures with backoff and halts on authorization/archive failures;
report and use the existing recovery path rather than editing state. Never delete
or overwrite files to force connection. Same remote identity (normalized URL +
workspace ID) resumes retained private state; a different identity does not
inherit it. Disconnect removes only this device binding and Key, retaining local
logs and private recovery state. No direct manipulation of device state.

Finish with root, workspace/type where known, binding and actual sync outcome,
material warnings or next action. No need for a separate document or Task merely
to report a simple connection.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
