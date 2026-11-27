import assert from "node:assert/strict";
import test from "node:test";
import { validateWorkspacePath } from "../server/domain/paths.ts";

test("workspace paths allow AGENTS.md and .vibe/ only", () => {
  for (const p of ["AGENTS.md", ".vibe/progress.md", ".vibe/tasks/t1.json", ".vibe/docs/specs/a.md"]) {
    assert.equal(validateWorkspacePath(p).ok, true, p);
  }
  for (const p of ["agents.md", "README.md", "src/a.ts", ".vibe", ".vibe/.sync/manifest.json", ".vibe/../x", "/AGENTS.md", "index.json", "members/a/b.md"]) {
    assert.equal(validateWorkspacePath(p).ok, false, p);
  }
  assert.equal(validateWorkspacePath(42).ok, false);
});
