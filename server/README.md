# Workbench server (single-user worklog sync)

Pure API server. It keeps one authoritative `AGENTS.md` plus a full `.vibe/` per workspace; the OpenCode plugin binds a project root with a workspace Key and syncs both ways. There is no web UI, no accounts, no members and no task board. Use Node 24+ (SQLite APIs). No runtime package dependencies.

## Run

Run `npm run start:team`. Configuration is read only from the server process environment.

| Variable | Meaning |
|---|---|
| `WORKBENCH_ADMIN_TOKEN` | Required, at least 32 characters. Static admin credential; startup fails without it. Never printed |
| `TEAM_HOST` | Default `127.0.0.1`; expose outside loopback only behind TLS |
| `TEAM_PORT` | Default `7410`; `0` picks a temporary port for tests |
| `TEAM_DB_PATH` | Default `team-data/workspace.sqlite` |
| `TEAM_TLS_CERT`, `TEAM_TLS_KEY` | Optional PEM paths; set both for HTTPS or neither for HTTP |

The startup line reports `adminToken: configured`. The data directory must be owner-only on Unix. Use a consistent SQLite backup (`VACUUM INTO` or online backup) and verify restore. Never copy a live WAL database as independent files.

## Credentials

- Admin: `Authorization: Bearer <WORKBENCH_ADMIN_TOKEN>`, valid on admin routes only.
- Key: `Authorization: Bearer <workspace Key>`, valid for its own workspace only. A Key on an admin route returns 403.
- The current Key and its hash are stored. The hash authenticates workspace requests; the current Key is returned on creation and through the admin-only `GET /api/workspaces/{id}/key` route. Keys never appear in request logs.

## API

Admin routes:

- `POST /api/workspaces` with `{name, type?}` creates a workspace (default type `engineering-dev`), writes the type template files and returns `{workspace, key}`. Unknown type: 422 `unsupported_type`.
- `POST /api/workspaces/import` with `{name,type,files:[{path,content}]}` creates a workspace and Key atomically, using exactly the supplied files; AGENTS.md and .vibe/progress.md required. 32 MiB encoded body, 1 MiB per file. No automatic retry on unknown result.
- `GET /api/workspaces`, `GET /api/workspaces/{id}`, `PATCH /api/workspaces/{id}` (rename), `DELETE /api/workspaces/{id}` (archive: data kept, Key stops working).
- `GET /api/workspaces/{id}/key` returns the current Key and requires the admin credential; archived workspaces return 404.

Key routes:

- `POST /api/connect` validates the Key and returns the workspace.
- `GET /api/workspaces/{id}/changes?since=0&limit=200` replays the change feed with no sequence gaps (includes tombstones).
- `GET/PUT/DELETE /api/workspaces/{id}/documents/{path}`. Mutations require `If-Match` (new path `0`); PUT body is `{content}` (UTF-8, at most 1 MiB). Conflicts return 409 with `currentVersion` and `currentHash`.
- Valid paths: `AGENTS.md` or anything under `.vibe/`, except the device-private `.vibe/.sync/` (case-insensitive) and unsafe/colliding cross-platform paths. Document PUT JSON is capped at 7 MiB; normal requests remain 2 MiB.
- An archived workspace answers 410 `workspace_archived`.

Health: `GET /api/healthz`. Request logs contain route, status and timing only, never bodies, headers or credentials.

## Storage

- Each document keeps one current version plus its latest 20 versions as an internal safety net. Tombstones are kept permanently.
- A change-feed cursor that lags behind pruned versions still reads a gapless feed: pruned upserts are coalesced into the current state, or reported as deletes when the document is deleted now.
- Schema v5 drops the team model (accounts, members, tokens, tasks, presence). Optional `Idempotency-Key` on document writes is workspace-scoped.
