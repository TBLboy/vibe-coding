# Shared team contracts

Protocol files used by both the headless workbench server and the OpenCode plugin. They define the path layout, the local binding record, the file manifest and the change-feed messages, so both sides read and write the same formats.

| File | Contract |
|---|---|
| `layout.ts` | Five memory layers plus `index.json`, and which server paths are valid |
| `binding.ts` | Directory-to-workspace binding record and its single-binding check |
| `manifest.ts` | Local file manifest, content hashing and local-change classification |
| `change-feed.ts` | Change messages the server returns for incremental sync |

## One copy per branch

The branches `feat/team-workspace-workbench` and `feat/team-workspace-plugin` each carry this directory, and it must stay byte-identical in both. There is no submodule and no package. Keep it free of server, SQLite, HTTP and OpenCode code.

Drift guard:

- `SHA256SUMS` lists every contract file and its test. Line endings are normalized before hashing.
- `contracts-sync.test.ts` fails when a file differs from the list or when a `.ts` file is not listed. It runs in `npm run test:core` on both branches.
- Release check: `git diff --exit-code feat/team-workspace-workbench feat/team-workspace-plugin -- shared/team-contracts`.

## Changing a contract

1. Make the change as one commit on one branch and run its tests.
2. Regenerate the list: `cd shared/team-contracts && shasum -a 256 binding.test.ts binding.ts change-feed.test.ts change-feed.ts layout.ts manifest.test.ts manifest.ts > SHA256SUMS` (add any new file to the command).
3. Cherry-pick the same commit onto the other branch and run its tests.
4. Run the release check above.
