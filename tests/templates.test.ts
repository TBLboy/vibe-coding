import assert from "node:assert/strict";
import test from "node:test";
import { DEFAULT_TYPE, getTemplate, listTypes } from "../server/templates/registry.ts";
import { validateWorkspacePath } from "../server/domain/paths.ts";

test("engineering-dev is the default and only registered type", () => {
  assert.equal(DEFAULT_TYPE, "engineering-dev");
  assert.deepEqual(listTypes(), ["engineering-dev"]);
  assert.equal(getTemplate("nope"), undefined);
  assert.equal(getTemplate("__proto__"), undefined);
});

test("engineering-dev template creates exactly the R1 file set", () => {
  const pack = getTemplate("engineering-dev");
  assert.ok(pack);
  assert.equal(pack.version, 1);
  assert.deepEqual(pack.files.map((f) => f.path).sort(), [
    ".vibe/docs/.gitkeep",
    ".vibe/lessons/README.md",
    ".vibe/progress.md",
    ".vibe/requirements/README.md",
    ".vibe/tasks/.gitkeep",
    "AGENTS.md",
  ]);
  for (const f of pack.files) {
    assert.equal(validateWorkspacePath(f.path).ok, true, f.path);
    assert.equal(f.content.includes("\r"), false, `CR in ${f.path}`);
  }
  assert.equal(pack.files.some((f) => f.path.startsWith(".vibe/sessions/")), false);
});

test("AGENTS.md carries one managed rules block and an empty project section", () => {
  const agents = getTemplate("engineering-dev")!.files.find((f) => f.path === "AGENTS.md")!.content;
  assert.equal(agents.split("<!-- VIBE-PROJECT-GENERAL:BEGIN -->").length, 2);
  assert.equal(agents.split("<!-- VIBE-PROJECT-GENERAL:END -->").length, 2);
  assert.ok(agents.includes("八荣八耻"));
  assert.ok(agents.includes("点拨"));
  assert.ok(agents.indexOf("## 项目级规则") > agents.indexOf("VIBE-PROJECT-GENERAL:END"));
  assert.ok(!agents.includes("workspace_"), "no sync instructions in AGENTS.md");
});
