import assert from "node:assert/strict";
import test from "node:test";
import { layerOf, validateServerPath } from "../shared/team-contracts/layout.ts";
import {
  buildMirrorPlan,
  projectServerPath,
  unprojectLocalPath,
} from "../runtime/core/team/projection.ts";

function assertValid(path: string): void {
  const result = validateServerPath(path);
  assert.equal(result.ok, true, `expected valid path: ${JSON.stringify(path)}`);
}

function assertInvalid(path: string, reason?: RegExp): void {
  const result = validateServerPath(path);
  assert.equal(result.ok, false, `expected invalid path: ${JSON.stringify(path)}`);
  if (result.ok === false && reason) assert.match(result.reason, reason);
}

test("validateServerPath accepts well-formed relative POSIX paths", () => {
  for (const path of [
    "index.json",
    "constitution/AGENTS.md",
    "specs/project.md",
    "specs/modules/auth.md",
    "work/T-1.json",
    "members/alice/progress.md",
    "activity/20261123T0920-alice.json",
    "specs/规格.md",
    "a/b/c/d.txt",
  ]) {
    assertValid(path);
  }
});

test("validateServerPath rejects absolute, empty, dot, backslash and control input", () => {
  assertInvalid("", /empty/);
  assertInvalid("/specs/a.md", /absolute/);
  assertInvalid("specs//a.md", /empty segment/);
  assertInvalid("specs/./a.md", /dot segment/);
  assertInvalid("specs/../a.md", /dot segment/);
  assertInvalid("specs/", /empty segment|trailing/);
  assertInvalid("specs\\a.md", /backslash/);
  assertInvalid("specs/\u0000a.md", /control/);
  assertInvalid("specs/\u001fa.md", /control/);
});

test("validateServerPath enforces segment and total length limits", () => {
  assertInvalid(`specs/${"a".repeat(256)}`, /segment/);
  assertValid(`specs/${"a".repeat(255)}`);
  const longTotal = Array.from({ length: 5 }, () => "a".repeat(250)).join("/");
  assert.ok(longTotal.length > 1024);
  assertInvalid(longTotal, /too long/);
});

test("layerOf classifies the five layers plus index", () => {
  assert.equal(layerOf("constitution/AGENTS.md"), "constitution");
  assert.equal(layerOf("specs/x.md"), "specs");
  assert.equal(layerOf("work/T-1.json"), "work");
  assert.equal(layerOf("members/alice/progress.md"), "members");
  assert.equal(layerOf("activity/e.json"), "activity");
  assert.equal(layerOf("index.json"), "index");
  assert.equal(layerOf("docs/x.md"), undefined);
  assert.equal(layerOf("index.jsonx"), undefined);
});

test("projectServerPath implements the projection table", () => {
  assert.deepEqual(projectServerPath("constitution/AGENTS.md"), {
    kind: "root",
    relativePath: "AGENTS.md",
  });
  assert.deepEqual(projectServerPath("constitution/skills/tdd/SKILL.md"), {
    kind: "root",
    relativePath: ".opencode/skills/tdd/SKILL.md",
  });
  assert.deepEqual(projectServerPath("constitution/skills/tdd/scripts/run.sh"), {
    kind: "root",
    relativePath: ".opencode/skills/tdd/scripts/run.sh",
  });
  for (const path of [
    "constitution/notes.md",
    "specs/modules/auth.md",
    "work/T-1.json",
    "members/alice/progress.md",
    "activity/20261123T0920-alice.json",
  ]) {
    assert.deepEqual(projectServerPath(path), { kind: "memory", relativePath: path });
  }
  assert.deepEqual(projectServerPath("index.json"), {
    kind: "memory",
    relativePath: "index.json",
  });
  assert.deepEqual(projectServerPath("docs/readme.md"), {
    kind: "unmapped",
    relativePath: "_unmapped/docs/readme.md",
    warn: true,
  });
});

test("projectServerPath throws on invalid paths", () => {
  assert.throws(() => projectServerPath("../escape"), /invalid path/);
});

test("unprojectLocalPath inverts every mapped projection", () => {
  const mapped = [
    "constitution/AGENTS.md",
    "constitution/skills/tdd/SKILL.md",
    "constitution/notes.md",
    "specs/modules/auth.md",
    "work/T-1.json",
    "members/alice/progress.md",
    "activity/20261123T0920-alice.json",
    "index.json",
  ];
  for (const serverPath of mapped) {
    const projection = projectServerPath(serverPath);
    assert.notEqual(projection.kind, "unmapped");
    if (projection.kind === "unmapped") continue;
    const local =
      projection.kind === "root"
        ? projection.relativePath
        : `.vibe/${projection.relativePath}`;
    assert.equal(unprojectLocalPath(local), serverPath);
  }
});

test("unprojectLocalPath refuses private, unmapped and foreign paths", () => {
  assert.equal(unprojectLocalPath(".vibe/.sync/manifest.json"), null);
  assert.equal(unprojectLocalPath(".vibe/_unmapped/docs/readme.md"), null);
  assert.equal(unprojectLocalPath("README.md"), null);
  assert.equal(unprojectLocalPath("specs/direct.md"), null);
  assert.equal(unprojectLocalPath("/AGENTS.md"), null);
  assert.equal(unprojectLocalPath(".vibe/specs/../x.md"), null);
  assert.equal(unprojectLocalPath(".vibe/constitution/AGENTS.md"), null);
  assert.equal(unprojectLocalPath(".vibe/constitution/skills/tdd/SKILL.md"), null);
  assert.equal(unprojectLocalPath(".vibe/constitution/notes.md"), "constitution/notes.md");
  assert.equal(unprojectLocalPath(".opencode/skills/tdd/SKILL.md"), "constitution/skills/tdd/SKILL.md");
});

test("buildMirrorPlan maps a mixed batch without collisions", () => {
  const plan = buildMirrorPlan([
    "constitution/AGENTS.md",
    "specs/a.md",
    "docs/x.md",
  ]);
  assert.equal(plan.batch.length, 3);
  assert.deepEqual(plan.collisions, []);
  const byPath = new Map(plan.batch.map((item) => [item.serverPath, item.local]));
  assert.deepEqual(byPath.get("specs/a.md"), { kind: "memory", relativePath: "specs/a.md" });
});

test("buildMirrorPlan reports duplicate targets as collisions", () => {
  const plan = buildMirrorPlan(["specs/a.md", "specs/a.md"]);
  assert.equal(plan.batch.length, 2);
  assert.deepEqual(plan.collisions, ["memory:specs/a.md"]);
});

test("buildMirrorPlan never targets the private .vibe/.sync area", () => {
  const plan = buildMirrorPlan(["docs/.sync/manifest.json", "constitution/AGENTS.md"]);
  for (const item of plan.batch) {
    const prefix = item.local.kind === "root" ? "" : ".vibe/";
    assert.ok(!`${prefix}${item.local.relativePath}`.startsWith(".vibe/.sync/"));
  }
});
