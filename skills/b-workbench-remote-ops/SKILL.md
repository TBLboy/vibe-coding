---
name: b-workbench-remote-ops
description: "操作 Workbench/管理工作空间/创建工作空间/查看工作空间 Key/重命名或归档工作空间/检查 Workbench 服务器/部署升级 Workbench/排查同步故障 · Operate the personal Workbench: workspaces, Keys, server health, deploy, upgrade, and sync troubleshooting."
license: MIT
compatibility: opencode
metadata:
  v2: true
  routing: explicit-only
---

# Workbench Operations

## Scope and authority

Explicit user requests only: workspace lifecycle, health, deployment/upgrade and
sync diagnosis. Local initialization/binding belongs to `a-workspace-connect`.
Read-only inspection does not authorize credential disclosure, creation, import,
archive, restart, migration, restore or deployment. Confirm destructive or
availability-affecting actions before executing; obey effective Policy. Never
change provider, user configuration or SSH settings as a side effect.

## Resolve the actual environment

Use the configured `WORKBENCH_URL`, confirmed SSH host/user, active service unit
and actual code/data paths; do not infer the deployment from a hardcoded address.
Previous personal deployment conventions (verify before use): `vibe-workbench.service`,
code `/home/ubuntu/vibe-workbench`, database `/home/ubuntu/vibe-data/workspace.sqlite`,
environment `/home/ubuntu/vibe-data/workbench.env`, SSH user `ubuntu`, port 22,
service port 8443. These are hints, not authority to contact a host. Verify identity
and configuration without dumping environment values. Server settings are
`TEAM_HOST`, `TEAM_PORT`, `TEAM_DB_PATH`, and paired `TEAM_TLS_CERT`/`TEAM_TLS_KEY`.
The administrator token is `WORKBENCH_ADMIN_TOKEN` in process environment; if
missing, ask the user to configure it securely, never search history. Prefer SSH
agent or existing approved key. Use verified HTTPS for public credentials; do not
bypass TLS validation or send real credentials to legacy public HTTP. Keep secrets
out of shell arguments, command traces, replies, logs, Git and Project Memory.
Only disclose a workspace Key to the authorized user when explicitly requested
or returned as the result of approved creation; redact it elsewhere. Never print
administrator tokens, SSH passwords or private keys. Workspace Keys are scoped
to one workspace; administrator credentials have broader authority.

## Health and diagnosis

Start with the least intrusive evidence: known host identity, service state and
recent redacted journal, disk/memory, Node version, configured listener (`ss -lnt`),
local then public `/api/healthz` using the actual protocol and address. A loopback
listener behind a reverse proxy can be intentional. Record schema version and
workspace count as health facts, not proof of a particular build; verify deployed
commit separately. For local-success/public-failure test DNS, TCP, firewall/cloud
security group, proxy, routing and TLS separately; do not assert one cause or
change network rules without evidence and authorization. Check authenticated list
only when needed and authorized. Never dump environment, secret-bearing config
or full document bodies to diagnose health.

## Workspace management

Admin routes use `Authorization: Bearer` from the environment, not a Key. Confirm
workspace ID (names may repeat), operation, scope and supported type. Use the
actual server response and redact all credentials except authorized Key disclosure.

| Operation | Request | Result / boundary |
|---|---|---|
| List | `GET /api/workspaces` | `{workspaces:[...]}` active only |
| Create blank | `POST /api/workspaces` `{name,type?}` | 201 `{workspace,key}`; default `engineering-dev` |
| Import | `POST /api/workspaces/import` `{name,type,files}` | Atomic creation, no template overlay |
| View Key | `GET /api/workspaces/{id}/key` | `{key}` current; archived not available |
| Rename | `PATCH /api/workspaces/{id}` `{name}` | `{workspace}` |
| Archive | `DELETE /api/workspaces/{id}` | `{archived:true}`; retained data, Key rejected with 410 |

For creation distinguish blank and existing logs. Import only the authorized root
and approved eligible files; check for sensitive content before transfer. Use
installed `${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}/runtime/opencode/plugins/vibe-v2/team/import-workspace.ts`
with Node `--experimental-strip-types`, arguments `root name type` and environment
`WORKBENCH_URL`, `WORKBENCH_ADMIN_TOKEN`. Requires AGENTS.md and `.vibe/progress.md`;
invalid/unsafe source, oversized content or changing source may be rejected; the
helper does not replace a review for secrets. No fallback to blank creation. Both
creation routes lack idempotency keys; if response is lost, inspect the workspace
list and resolve ambiguity before retrying. Archive requires explicit confirmation;
it is not a purge. Key rotation is not exposed by the current public API; do not
invent an endpoint or modify database records to rotate it.

## Deployment and recovery

For an authorized upgrade: identify source/target commits, actual unit/config,
required Node version, database/schema compatibility and backup/restore plan.
Validate code and paired template compatibility in isolation before changing live
service. Use a database-native consistent online backup (e.g. `VACUUM INTO` to
an unused destination), verify integrity and isolated restore, protect backup
permissions. Never copy a live WAL database as independent files. Preserve service
configuration and environment secrets (owner-only files) unless approved changes
are necessary. Deploy only the intended commit; do not reset unrelated changes.
Confirm restart/downtime, then check running service, listener, local/public
health, authenticated list and scoped sync smoke using disposable test data only
when authorized. Upgrade Workbench before the companion Plugin when their
contracts change. A health response alone is not end-to-end acceptance.

On migration/startup failure stop further changes and preserve diagnostics; do
not retry blindly. Restore only with user approval and a consistent backup,
considering any writes since backup; plan downtime and recovery of those writes.
Do not delete the database, WAL files, environment or backups to force startup.
Archived data and historical backups stay unless explicitly authorized for removal.

## Sync troubleshooting

Distinguish binding, connectivity, authentication, file eligibility, conflicts,
client state and server behavior. Use actual `workspace_status`/sync results,
redacted logs and server health, not polling or direct private-state edits.
`401` suggests credentials; `403` wrong audience/scope; `410 workspace_archived`
means the binding cannot sync; `409` is a version conflict; timeouts can be
transient. The change feed `GET /api/workspaces/{id}/changes?since=<cursor>&limit=<n>`
requires that workspace's Key, not the administrator token. Compare cursor and
actual response metadata only if authorized; do not export document contents.
A pending count alone does not identify the cause. Conflicts require user choices
via `a-workspace-connect`; do not choose a side. Database lock/corruption requires
non-destructive diagnosis first, approval before stop/restore. Report facts,
affected scope, action taken, verification and next step; no new operations panel.

## V2 operating rules

Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.
