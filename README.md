# Vibe Coding V2 — Personal Workbench

This branch is the API-only personal engineering log service (Node.js + SQLite V5). The companion plugin contains the OpenCode Runtime and Skills. There are no accounts, members, team tasks or web management UI. See [server guide](server/README.md) for configuration and API.

Workbench is the primary initializer. Empty creation uses the engineering-dev six-file template; explicit local initialization uses the generated companion pack; existing logs can be imported atomically via `/api/workspaces/import`. Git remains independent.

## Run locally

Node 24+ recommended. Set a strong `WORKBENCH_ADMIN_TOKEN` securely in the process environment; use a dedicated owner-only data directory and HTTPS before exposing the service publicly.

```sh
npm ci
npm run verify
npm run start:team
```

The template source is `server/templates/`; export the paired plugin pack with `node --experimental-strip-types scripts/export-template.ts <companion>/shared/team-contracts/templates/engineering-dev.json`. The companion's local-init test compares the actual exported bytes and installed output. Do not independently edit the generated pack.

See `docs/` for the retained V2 contracts. Historical verification/roadmap files refer to earlier versions, not proof of current production acceptance. Real OpenCode/model and cloud deployment are separate acceptance gates.
