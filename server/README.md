# Team workspace server (M1 T4)

Opt-in server; the single-user plugin does not start it. Use Node 24+ for the
SQLite lifecycle/transaction APIs (Node 22.16+ needs `--experimental-sqlite`). No runtime
package dependencies. Current automated checks run on Node 26.10.0.

## Run and provision

Run `npm run start:team`. Configuration is read only from the server process's
environment; it does not read or modify OpenCode configuration.

| Variable | Default / meaning |
|---|---|
| `TEAM_HOST` | `127.0.0.1`; expose outside loopback only behind your TLS/deployment boundary |
| `TEAM_PORT` | `7410`; `0` chooses a temporary port for tests |
| `TEAM_DB_PATH` | `team-data/workspace.sqlite`, ignored by this repository |
| `TEAM_ORG_ID` | `org_default`; one configured organization per server |
| `TEAM_BOOTSTRAP_EMAIL`, `TEAM_BOOTSTRAP_PASSWORD` | Required only when this org has no accounts |
| `TEAM_BOOTSTRAP_NAME` | Optional first-account display name |

Inject passwords securely into the environment, not into source, shell history,
logs or git. The data directory must be owner-only on Unix; a new directory is
created as `0700`, and the SQLite file is `0600`. Existing directory permissions
are never silently changed. Windows deployments must enforce equivalent ACLs.

There is no anonymous signup API. To provision another internal account, supply
`TEAM_ACCOUNT_EMAIL`, `TEAM_ACCOUNT_PASSWORD`, optional `TEAM_ACCOUNT_NAME` and
the same database/org configuration, then run:

```sh
npm run start:team -- provision-account
```

Provisioning refuses a duplicate email; neither provisioning nor normal startup
resets existing passwords. `SIGTERM` / `SIGINT` closes HTTP before SQLite. Stop
the server (or use a proper SQLite backup/checkpoint) before copying database
files; a live WAL database is not safely backed up by copying the main file alone.

## API boundaries

- Account session: `POST /api/auth/login`, `GET/POST /api/workspaces`,
  `POST /api/connect`, membership requests and invitation acceptance.
- Workspace token: metadata/members, owner invitations/approvals/removal/key
  rotation, documents and change feed. Scope and current membership are checked
  on every request. All active members may read all workspace documents.
- Invitation acceptance: `POST /api/workspaces/{id}/invitations/accept`; a key
  alone, pending invitation or pending application never grants log access.
- Requests: `POST /api/workspaces/{id}/requests`; owner approval is
  `POST /api/workspaces/{id}/members/{accountId}/decide` with `{approve:true|false}`.
- Documents: `GET/PUT/DELETE /api/workspaces/{id}/documents/{path}`. Mutations
  require `If-Match` (new path `0`). PUT body is `{content:"..."}`. Owner writes
  shared layers; members write only their own namespace; system layers reject
  direct writes. Conflicts expose version/hash, not document content.
- `GET /api/workspaces/{id}/changes?since=0&limit=200` replays immutable versions
  with no sequence gaps. Requests <=2 MiB, documents <=1 MiB, feeds <=8 MiB.
- Key rotation blocks future connections using the previous key; an already
  issued workspace token retains its own TTL. Removal revokes that member's
  workspace tokens; rejoining does not revive them. Session TTL is 30 days,
  workspace token TTL 7 days; passwords use scrypt.
- Login throttling uses normalized email and direct socket IP: five failures per
  15-minute window; pending password checks reserve those slots too. Forwarded IP
  headers are not trusted. Successful login does not erase other in-flight checks.
- Optional `Idempotency-Key` is workspace-scoped and includes account/request
  identity in its fingerprint. Regular replies replay, different requests return
  409. Credential-producing replies are never cached: a repeated rotation key
  returns 409 without another rotation. Use a new request key if another one-time
  key is needed. Account-scoped workspace creation rejects this header; login
  and connect do not offer mutation replay.
- Health is `/api/healthz`; `/api/metrics` requires an account session. Structured
  request logs contain route/status/timing, never body, headers, passwords or tokens.

Task/board APIs and plugin synchronization are the next M1 slices, not claimed
implemented by this T4 server foundation. TLS and real deployment remain operator
responsibilities; these local HTTP/SQLite tests are not a production security audit.
