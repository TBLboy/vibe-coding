import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");

test("Task schema is valid JSON and declares only the minimal Task contract", () => {
  const schema = JSON.parse(readFileSync(resolve(root, "schemas/task.schema.json"), "utf8"));
  assert.equal(schema.type, "object");
  assert.equal(schema.additionalProperties, false);
  assert.ok(schema.required.includes("policy"));
  assert.ok(schema.required.includes("verification"));
  assert.ok(!schema.properties.run);
  assert.ok(!schema.properties.evidence);
  assert.ok(!schema.properties.goalRuntime);
});

test("OpenCode config has a primary Agent and no third-party integration bundle", () => {
  const config = JSON.parse(readFileSync(resolve(root, "runtime/opencode/opencode.json"), "utf8"));
  assert.equal(config.default_agent, "vibe-main");
  assert.equal(config.subagent_depth, undefined);
  assert.deepEqual(config.plugins, ["./runtime/opencode/plugins/vibe-v2"]);
  assert.equal(config.mcp, undefined);
  assert.equal(config.model, undefined);
  assert.equal(config.provider, undefined);
});

test("plugin queues mode changes and enforces a strict-only reviewer permit", () => {
  const plugin = readFileSync(resolve(root, "runtime/opencode/plugins/vibe-v2/index.ts"), "utf8");
  assert.match(plugin, /delivery: "queue"/);
  assert.match(plugin, /vibe_set_session_mode/);
  assert.match(plugin, /vibe_task_control/);
  assert.match(plugin, /ctx\.permission\.hook\("evaluate"/);
  assert.match(plugin, /canAuthorizeReview\(task, activeValue\.taskID\)/);
  assert.match(plugin, /event\.effect = "deny"/);
});

test("reviewer configuration is read-only and has no shell permission", () => {
  const reviewer = readFileSync(resolve(root, "runtime/opencode/agents/vibe-reviewer.md"), "utf8");
  assert.match(reviewer, /mode: subagent/);
  assert.match(reviewer, /action: "\*"[\s\S]*effect: deny/);
  assert.doesNotMatch(reviewer, /action: edit[\s\S]*effect: allow/);
  assert.doesNotMatch(reviewer, /action: shell/);
  assert.doesNotMatch(reviewer, /action: glob/);
  assert.doesNotMatch(reviewer, /action: grep/);
  assert.match(reviewer, /resource: "\*\*\/.env"[\s\S]*effect: deny/);
});

test("the new pack has no legacy upgrade or migration entrypoints", () => {
  assert.equal(existsSync(resolve(root, "AI_INSTALL.md")), false);
  assert.equal(existsSync(resolve(root, "AI_UPGRADE.md")), false);
  assert.equal(existsSync(resolve(root, "runtime/core/legacy-migration.ts")), false);
});

const V2_SKILLS = [
  "a-architecture-decision", "a-business-clarify", "a-business-code-align", "a-project-archive",
  "a-codebase-onboarding", "a-deep-research", "a-engineering-landing",
  "a-engineering-spec", "a-paper-reading", "a-project-context-briefing",
  "a-requirement-baseline", "a-retrospective", "a-task-decompose", "a-verification",
  "b-concise-communication", "b-jetson-robot-policy-deployment",
  "b-multi-role-ux-audit", "b-opencode-model-config", "b-plan-stress-test",
  "b-scenario-product-walkthrough", "b-skill-authoring", "b-source-code-tutoring",
  "b-web-research-tooling",
];

test("managed capability Skills are V2-compatible and routed by the main Agent", () => {
  const skillRoot = resolve(root, "skills");
  assert.deepEqual(readdirSync(skillRoot).sort(), [...V2_SKILLS].sort());
  const main = readFileSync(resolve(root, "runtime/opencode/agents/vibe-main.md"), "utf8");
  for (const id of V2_SKILLS) {
    const content = readFileSync(resolve(skillRoot, id, "SKILL.md"), "utf8");
    assert.match(content, /^---\nname: /, id);
    assert.match(content, /metadata:\n  v2: true/, id);
    assert.match(content, /Use only the V2 Task JSON and V2 Project Memory locations/, id);
    assert.doesNotMatch(content, /\.project-log|SQLite|event ledger|standalone Evidence/, id);
    assert.match(main, new RegExp("`" + id + "`"), id);
  }
  assert.doesNotMatch(main, /old Project Log|\.project-log|Goal\/Run\/Evidence\/ledger\/SQLite/, "routing");
});
