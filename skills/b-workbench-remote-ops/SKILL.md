---
name: b-workbench-remote-ops
description: "远端 Workbench 运维/部署 Workbench/检查 Workbench 服务器/配置 Workbench 连接 · Explicitly inspect, deploy, upgrade, or verify the personal Workbench server and connect a local plugin to it."
license: MIT
compatibility: opencode
metadata:
  v2: true
  routing: explicit-only
---

# Remote Workbench Operations

Use only when the user explicitly asks to inspect, deploy, upgrade, configure, or troubleshoot the personal remote Workbench. This Skill owns the server connection procedure and local client configuration; it does not silently run remote commands.

## Current connection defaults

- Workbench API: `http://49.233.90.195:8443`
- SSH host: `49.233.90.195`
- SSH user: `ubuntu`
- SSH port: `22`
- Workbench service: `/home/ubuntu/vibe-workbench`
- Database: `/home/ubuntu/vibe-data/workspace.sqlite`

The API currently uses HTTP for this personal deployment. Treat the endpoint as sensitive until HTTPS is configured.

## Credentials

- Never store, commit, print, or repeat the SSH password.
- Prefer the local SSH private key at the user's configured SSH agent or `~/.ssh/id_ed25519`.
- The administrator token for this personal Workbench is available in the local Skill configuration below; use it only when an admin API call is explicitly requested and never print it in output.
- The administrator token manages all workspaces. A workspace Key is narrower and belongs only in the plugin's device-private binding state.
- If a credential is missing, ask the user for it once. Do not guess, rotate, or write it into project files.

Administrator token (personal deployment):

```text
WORKBENCH_ADMIN_TOKEN=a3df38775c416da6e813ba4523def94e558c66a20e350ab37c4eb1d4960ab64b
```

## Inspect the server

1. Connect with SSH using the configured key and verify `whoami`, hostname, Node version, service status, listeners, disk space, and database location.
2. Check the API locally on the server with `/api/healthz`.
3. From the user's machine, check TCP `8443` and the same health endpoint.
4. If local health succeeds but public access fails, inspect the cloud security-group rule for TCP `8443`; the SSH session cannot change the cloud provider's external rule.
5. Report confirmed facts and stop before changing a running service unless the user asked for deployment or repair.

## Deploy or upgrade

1. Back up the database and its `-wal`/`-shm` files before changing code or schema.
2. Fetch the approved Workbench branch and verify the intended commit before restarting.
3. Keep `WORKBENCH_ADMIN_TOKEN` in a root-readable or service-user-readable environment file outside Git, with restrictive permissions.
4. Configure `TEAM_HOST=0.0.0.0`, `TEAM_PORT=8443`, and a persistent `TEAM_DB_PATH`.
5. Restart through systemd, then verify the process, listener, local health endpoint, public health endpoint, and authenticated admin endpoint.
6. Record only durable deployment facts in `.vibe/progress.md`; never record credentials.

## Connect a local project

Set the machine-level plugin endpoint:

```text
WORKBENCH_URL=http://49.233.90.195:8443
```

Use `a-workspace-connect` for the actual project binding. Do not place the administrator token in `WORKBENCH_URL`, `.vibe/`, a Task, or a progress file. Use the workspace Key only through `workspace_connect`.

## Safety boundaries

- Do not delete the database, reset the repository, or change the SSH configuration without explicit user instruction.
- Do not expose `8443` as HTTPS unless a certificate and client trust plan are configured; HTTP is the current personal test deployment.
- Do not create a workspace merely to test connectivity; use health and authenticated list endpoints unless the user supplies a workspace name and asks for creation.
- Do not claim public access works until it has been tested from the client machine.

## V2 operating rules

- For registered Tasks, use Runtime lifecycle events in `docs/03-STATE-MACHINE.md`; never edit Task JSON directly.

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
