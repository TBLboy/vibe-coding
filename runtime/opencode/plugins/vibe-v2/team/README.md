# Opt-in team workspace plugin (M1 T6)

These modules extend the existing V2 plugin. They do not create a second plugin,
provider, permission profile, MCP server or background poller. Without a valid
`.vibe/.sync/binding.json`, setup registers no extra tools/hooks and does no team
network work or mirror writes.

## First connection

Create/join the server workspace, authenticate with `/api/auth/login`, and obtain
the current workspace task-key from its owner. Inject the following environment
variables securely (do not put actual secrets in prompts, source or shell history):

- `TEAM_SERVER_URL`: server origin/base URL, without `/api`, query or credentials.
- `TEAM_SESSION_TOKEN`: account session returned by login.
- `TEAM_TASK_KEY`: workspace task-key, not an account credential.

Run the explicit local connector using Node with strip-types support:

```sh
node --experimental-strip-types runtime/opencode/plugins/vibe-v2/team/connect.ts /absolute/workspace/root
```

For the installed pack, use the same path under `~/.config/opencode/` instead.
The connector resolves the canonical Git memory root / nearest existing ancestor
owning `.vibe/`, never creates another log root in a code subdirectory, and checks
the existing workspace/server/account binding before updating credentials.
Repository URLs and current branches do not affect connection or reconnect;
there is no bypass flag or second confirmation. It never clones or changes Git
state. Then use `/reload` to load tools;
no global bootstrap tool is registered for unbound single-user projects.

The server's connect reply supplies the authenticated `accountId`; caller text
does not choose local write identity. The private directory holds `binding.json`,
`credentials.json` (workspace token only, Unix `0600`) and `manifest.json`. Session
tokens/task-keys are not saved. A missing/corrupt manifest or orphaned pre-binding
sync state requires inspection, not an automatic reset that might lose history.
Equivalent private ACLs must be enforced on Windows.

## Bound operation

Each primary, matching-project context turn runs one cooperative 1500ms sync,
then adds a <=2000-character read-only data summary. Reviewer/child Sessions and
unrelated project Sessions do not sync; workspace tool executors enforce the same
root/primary-Agent checks. No event stream or long connection.

Connect, timer and tool syncs use a 10-second budget instead, so a slow network
does not turn a successful request into a spurious `network_unavailable`; the
shorter per-turn budget only bounds the context injection.

A bound project also runs a **background sync timer**, because otherwise local
edits would only reach the server when a turn starts. Interval defaults to 10
seconds; `VIBE_TEAM_SYNC_INTERVAL_MS` overrides it and `0` disables it. Runs are
serialized, so a slow sync never overlaps the next tick and a concurrent
turn-triggered sync surfaces only as a busy skip. The timer is unref'd so it never
keeps the host process alive, and it is cleared when the plugin is reloaded.
Background sync stops when OpenCode exits; it is not a separate daemon.

Tools: `workspace_connect` (reconnect an already-bound workspace),
`workspace_status`, `workspace_sync`, `workspace_record_progress`,
`workspace_task_declare`, `workspace_task_claim`, `workspace_task_update`, and
`workspace_query_spec`. Reconnect takes no arguments and reads fresh session token
and key only from fixed `TEAM_SESSION_TOKEN` / `TEAM_TASK_KEY` process environment
variables. Credentials never enter the native tool inputs that can become Session
history. If those variables are not available in the host, use the explicit local
connector again for the same root/binding; the next sync reads refreshed private
credentials. Do not paste secrets into prompts/tools or change unrelated host
configuration to provide them.
Task tools send one idempotency-keyed request and never queue/retry automatically.
Progress append/replace writes the current member's local file first, then syncs;
offline results explicitly say `saved_locally`. A version conflict is preserved
and warned, never silently merged or blindly retried.

Sync checkpoints confirmed file/manifest changes individually. Cursor advances
only after each contiguous validated change is applied. Historical events cannot
overwrite a known newer version. For absent/untracked incoming upserts, a current
document read prevents replay resurrecting an already-acknowledged deletion;
this costs extra requests but avoids a second tombstone/outbox state model.
The initial baseline is pulled before considering new untracked candidates.

Unauthorized edits restore authoritative content, first preserving different
local bytes as `*.conflict-<UTC>-<random>`; locally missing unauthorized files
restore too. A tombstone only removes a tracked, reversible target after a final
snapshot check; changed bytes are preserved first. Untracked files, known copy/
conflict/temp artifacts and `_unmapped` deletion targets are never auto-deleted.
Unknown server paths mirror under `_unmapped/` and warn. Symlinks, case aliases,
file/directory collisions, unsafe paths and stale local snapshots fail closed.
Atomic writes use a fixed-size `.tmp-<UUID>` sibling basename rather than extending
the target name. Conflict copies retain the original prefix where it fits, trimming
only that prefix at UTF-8 code-point boundaries so the full basename stays <=255
bytes. Progress append/replace also checks the captured old hash (including an
absent file); an intervening editor save fails closed without upload or overwrite.

HTTP aborts at the remaining deadline, refuses redirects, requests >2 MiB and
responses >9 MiB; document pushes remain <=1 MiB before JSON encoding.
Network failures back off 15/30/60/120s; auth loss stops automatic attempts until
fresh reconnect credentials arrive. Filesystem operations are cooperative and
complete under the lock; there is no detached timed-out writer. OS-stalled I/O
cannot be hard-cancelled, and this is not a sandbox against hostile concurrent
local filesystem mutation.

The wx lock contains pid/time/nonce; dead-process locks older than ten minutes
can be reclaimed under a separate acquisition guard. Live/invalid locks fail
closed. A crash during guard acquisition can leave `lock-claim.json`: stop all
instances and inspect before explicitly clearing that guard. Never clear a live
writer's lock. Failed writes keep existing bytes; startup does not erase mirrors.

Tests use the real plugin setup with simulated host APIs, fake HTTP and temporary
filesystem/Git fixtures. Real two-client server integration and installed OpenCode
team smoke remain T7/release acceptance, not implied by these local checks.
