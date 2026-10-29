import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const root = resolve(import.meta.dirname, "..");
// Source files are checked out with the platform line ending (Git autocrlf on
// Windows produces CRLF), so compare normalized text instead of assuming LF.
const readNormalized = (relative: string) =>
  readFileSync(resolve(root, relative), "utf8").replace(/\r\n/g, "\n");

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
  assert.deepEqual(config.plugin, ["./runtime/opencode/plugins/vibe-v2"]);
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
  assert.match(plugin, /resolveMemoryRoot\(/, "plugin resolves one memory root per project");
  assert.match(plugin, /validateTaskRecord\(task, taskID\)/, "plugin validates Task records");
  assert.match(plugin, /reviewCompletionStorageKey\(event\.sessionID\)/, "permit consumption records reviewer invocation");
  assert.match(plugin, /canCloseTask\(task, taskID, reviewerInvoked\)/, "strict close checks reviewer invocation");
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
  "a-architecture-decision", "a-business-clarify", "a-business-code-align", "a-project-archive", "a-project-init",
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
  const main = readNormalized("runtime/opencode/agents/vibe-main.md");
  for (const id of V2_SKILLS) {
    const content = readNormalized(`skills/${id}/SKILL.md`);
    assert.match(content, /^---\nname: /, id);
    assert.match(content, /metadata:\n  v2: true/, id);
    assert.match(content, /Use only the V2 Task JSON and V2 Project Memory locations/, id);
    assert.doesNotMatch(content, /\.project-log|SQLite|event ledger|standalone Evidence/, id);
    assert.doesNotMatch(content, /\.vibe\/requirements\.md/, `${id}: requirement baselines are per work under .vibe/requirements/`);
    assert.match(main, new RegExp("`" + id + "`"), id);
    const sections = content.split("\n").filter((line) => /^## /.test(line) && !/^## V2 operating rules/.test(line));
    assert.ok(sections.length >= 2, `${id} must carry its full methodology, not a stub (found ${sections.length} sections)`);
    assert.ok(content.split("\n").length >= 30, `${id} is too short to be a complete Skill`);
  }
  assert.ok(existsSync(resolve(root, "skills/b-opencode-model-config/scripts/configure_models.py")));
  assert.ok(existsSync(resolve(root, "skills/b-source-code-tutoring/references/teaching-template.md")));
  assert.ok(existsSync(resolve(root, "skills/a-project-init/templates/general-rules.md")));
  assert.doesNotMatch(main, /old Project Log|\.project-log|Goal\/Run\/Evidence\/ledger\/SQLite/, "routing");
});

test("memory contract defines per-work requirement baselines with an index", () => {
  const contract = readNormalized("docs/05-MEMORY-CONTRACT.md");
  assert.match(contract, /\.vibe\/requirements\/<work>\.md/);
  assert.match(contract, /\.vibe\/requirements\/README\.md/);
  assert.doesNotMatch(contract, /\.vibe\/requirements\.md/);
  const baseline = readNormalized("skills/a-requirement-baseline/SKILL.md");
  assert.match(baseline, /README\.md/);
  assert.match(baseline, /draft.*active.*superseded/);
});
