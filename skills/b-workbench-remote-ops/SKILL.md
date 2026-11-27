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

Use only when the user explicitly asks to operate the personal Workbench: create, list, rename or archive a workspace, view a workspace Key, check the server, deploy or upgrade it, or troubleshoot sync. This Skill owns the server side and the workspace lifecycle.

Connecting a local project root with a workspace Key is a different job: hand that off to `a-workspace-connect`.

## 1. Connection facts

- Workbench API: `http://49.233.90.195:8443`
- SSH host: `49.233.90.195`, user `ubuntu`, port `22`
- Service: `vibe-workbench.service`, code at `/home/ubuntu/vibe-workbench`
- Database: `/home/ubuntu/vibe-data/workspace.sqlite` (plus `-wal`/`-shm`)
- Environment file: `/home/ubuntu/vibe-data/workbench.env`
- Deployment is HTTP for personal use; treat the endpoint as sensitive until HTTPS is configured.

Administrator token (personal deployment):

```text
WORKBENCH_ADMIN_TOKEN=a3df38775c416da6e813ba4523def94e558c66a20e350ab37c4eb1d4960ab64b
```

Credential rules:

- Never print, echo or repeat the administrator token or the SSH password in replies, logs or files.
- Never write a workspace Key into a project file, `.vibe/`, a Task or `progress.md`.
- Prefer the local SSH key (`~/.ssh/id_ed25519`) or the SSH agent.
- The administrator token manages every workspace; a workspace Key reaches exactly one.

## 2. Health checks

Read-only, safe to run when asked to "check Workbench":

1. Server identity: `whoami`, hostname, `node --version`, disk, memory.
2. Service: `systemctl status vibe-workbench.service --no-pager`, recent journal lines.
3. Listener: `ss -lnt | grep ':8443 '` must show `0.0.0.0:8443`.
4. Local health: `curl -fsS http://127.0.0.1:8443/api/healthz` → `{ok, schemaVersion, workspaceCount}`.
5. Public health from the user's machine: TCP `8443` plus the same endpoint.
6. If local health works but public fails, the cause is outside the host: check the cloud security-group rule for inbound TCP `8443`. SSH cannot change it.
7. Report schema version and workspace count so the user sees which build is live.

## 3. Workspace management

All routes below require `Authorization: Bearer <administrator token>`.

| Operation | Request | Notes |
|---|---|---|
| List | `GET /api/workspaces` | Active workspaces only; returns `{id,name,type,createdAt}` |
| Create | `POST /api/workspaces` `{name, type?}` | 201 `{workspace, key}`; default type `engineering-dev`; unknown type 422 `unsupported_type` |
| View Key | `GET /api/workspaces/{id}/key` | Returns the current Key; archived workspace 404 |
| Rename | `PATCH /api/workspaces/{id}` `{name}` | |
| Archive | `DELETE /api/workspaces/{id}` | Data kept; the Key immediately returns 410 `workspace_archived` |

Rules:

- One workspace has exactly one current Key. A new Key replaces the old one and the old stops working.
- Creating writes the type template files in the same transaction, so a new workspace already contains `AGENTS.md` and the `.vibe/` skeleton.
- Report a newly created Key once, in the reply that answers the request, and never store it in project memory.
- Archiving is destructive for connections: confirm with the user before calling `DELETE`.

## 4. Deployment and upgrade

Only when the user asks to deploy or upgrade:

1. Back up `workspace.sqlite`, `-wal` and `-shm` to a timestamped directory; record the path.
2. Fetch the approved branch, check out the intended commit, and report the commit hash.
3. Keep `WORKBENCH_ADMIN_TOKEN` in `workbench.env` (owner-readable, mode 600), never in Git.
4. Run with `TEAM_HOST=0.0.0.0`, `TEAM_PORT=8443`, persistent `TEAM_DB_PATH`.
5. Restart via `systemctl restart vibe-workbench.service`; confirm `Restart=on-failure` and `enabled`.
6. Verify: process running, listener on `0.0.0.0:8443`, local health, public health, authenticated list.
7. A schema bump migrates on startup; if it fails, restore the backup and report instead of retrying blindly.

## 5. Sync troubleshooting

- `401` from the plugin: the Key is wrong or was replaced. Ask the user to re-check it; do not guess variants.
- `410 workspace_archived`: the workspace was archived; the plugin stops until the user reconnects to another workspace.
- Public timeout with healthy local health: cloud security-group rule.
- Plugin reports conflicts: that is not a server fault; hand off to the conflict flow (`workspace_resolve_conflict`).
- Plugin reports `pending` and never drains: compare `GET /api/workspaces/{id}/changes` behavior and the plugin's `WORKBENCH_URL`; a wrong base URL is the common cause.
- Database locked or corrupt: stop the service, keep the files for inspection, restore the latest backup with the user's approval.

## 6. Data handling

- Never delete the database, `workbench.env`, or backups without explicit user instruction.
- Delete old backups only when asked; keep at least the most recent one.
- Data for an archived workspace is retained; do not purge it.

## 7. Boundaries

- Do not create or edit `AGENTS.md` or `.vibe/` in a local project; Workbench creates them.
- Do not perform project binding; that is `a-workspace-connect`.
- Do not resolve sync conflicts on the user's behalf.
- Do not rotate Keys or change SSH configuration unless explicitly requested.
- Ask before: archiving a workspace, restarting the service, `git reset`, deleting data, editing SSH configuration.

## V2 operating rules

- For registered Tasks, use Runtime lifecycle events in `docs/03-STATE-MACHINE.md`; never edit Task JSON directly.

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
