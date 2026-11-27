import assert from "node:assert/strict";
import test from "node:test";
import { openTeamDatabase } from "../server/store/sqlite.ts";
import { archiveWorkspace, createWorkspace, getWorkspace, listWorkspaces, renameWorkspace } from "../server/domain/workspace.ts";
import { findWorkspaceByKey } from "../server/domain/key.ts";
import { getDocument } from "../server/domain/documents.ts";
import { getChanges } from "../server/domain/changes.ts";
import { ApiError } from "../server/http/errors.ts";

const NOW = Date.parse("2026-11-27T00:00:00.000Z");

test("create defaults to engineering-dev and writes exactly the template files", () => {
  const store = openTeamDatabase(":memory:");
  try {
    const { workspace, key } = createWorkspace(store, { name: "My Work" }, NOW);
    assert.equal(workspace.type, "engineering-dev");
    assert.equal(findWorkspaceByKey(store, key)?.workspaceId, workspace.id);
    const batch = getChanges(store, { workspaceId: workspace.id, since: 0 });
    assert.deepEqual(batch.changes.map((c) => c.path).sort(), [
      ".vibe/docs/.gitkeep", ".vibe/lessons/README.md", ".vibe/progress.md",
      ".vibe/requirements/README.md", ".vibe/tasks/.gitkeep", "AGENTS.md",
    ]);
    assert.ok(getDocument(store, { workspaceId: workspace.id, path: "AGENTS.md" })?.content?.includes("八荣八耻"));
  } finally { store.close(); }
});

test("unknown type is rejected with 422 and creates nothing", () => {
  const store = openTeamDatabase(":memory:");
  try {
    assert.throws(() => createWorkspace(store, { name: "x", type: "nope" }, NOW),
      (e) => e instanceof ApiError && e.status === 422 && e.code === "unsupported_type");
    assert.equal(listWorkspaces(store).length, 0);
  } finally { store.close(); }
});

test("rename and archive: archived space leaves the list and its Key reports archived", () => {
  const store = openTeamDatabase(":memory:");
  try {
    const { workspace, key } = createWorkspace(store, { name: "A" }, NOW);
    assert.equal(renameWorkspace(store, workspace.id, { name: "B" }).name, "B");
    archiveWorkspace(store, workspace.id, NOW + 1);
    assert.deepEqual(listWorkspaces(store), []);
    assert.equal(findWorkspaceByKey(store, key)?.archived, true);
    assert.throws(() => getWorkspace(store, workspace.id), (e) => e instanceof ApiError && e.status === 404);
  } finally { store.close(); }
});
