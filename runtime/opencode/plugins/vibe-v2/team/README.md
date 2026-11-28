# Personal Workbench plugin

Workbench is the primary initializer: create a workspace (blank canonical template or import existing logs), then bind the actual project memory root using its Key. Explicit local initialization is available via the installed `team/init-local.ts` (Node `--experimental-strip-types`, arguments `root engineering-dev`); the generated pack is distributed with the installer.

The existing `workspace_connect` tool validates the Key and attempts first sync. The CLI `connect.ts` only binds using `WORKBENCH_URL` and `WORKBENCH_KEY`; reload the host to enable tools and automatic sync. `workspace_status`, `workspace_sync`, `workspace_disconnect` and `workspace_resolve_conflict` keep their existing roles. Sync runs automatically at the configured interval (default 10s). No account, members, Task Key or team collaboration. Git independently manages code.

`AGENTS.md` and `.vibe/` shared files are synchronized. `.vibe/.sync` and temporary local files are excluded; unsafe paths/bytes are never overwritten silently. Device state under OPENCODE_CONFIG_DIR/vibe-worklog is separate from project memory; manifest/conflicts/recoveries/status are per remote identity. Old bound state migrates under the private lock; unowned legacy data is preserved separately. Do not manually combine old and new states. If a process crashes and leaves operation.lock, confirm the owning process is no longer running before removing that lock; preserve all other files. Recovery files can be inspected manually and are never uploaded or automatically deleted.

For import, use installed `team/import-workspace.ts` with root, name, type and environment WORKBENCH_URL/WORKBENCH_ADMIN_TOKEN. Use HTTPS for public admin requests. Failure after sending may mean unknown outcome; query the workspace list before retry.

Use the existing installer for paired releases. Real OpenCode/model and cloud deployment require separate validation.
