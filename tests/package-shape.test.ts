import assert from "node:assert/strict";
import { createHash } from "node:crypto";
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

test("plugin entry delegates to the tested host adapter", () => {
  const plugin = readNormalized("runtime/opencode/plugins/vibe-v2/index.ts");
  assert.match(plugin, /Plugin\.define/);
  assert.match(plugin, /setup\(ctx/);
  assert.ok(existsSync(resolve(root, "runtime/opencode/plugins/vibe-v2/setup.ts")));
});

test("every runtime child process is hidden on Windows", () => {
  // Without `windowsHide`, each git call from the plugin flashes a console window
  // on Windows because the plugin shells out while rendering Session context.
  const sources = [
    "runtime/opencode/plugins/vibe-v2/setup.ts",
    "runtime/core/artifact-evidence.ts",
  ];
  for (const relative of sources) {
    const content = readNormalized(relative);
    const calls = content.split("\n").filter((line) => /execFileSync\(|execSync\(|spawnSync\(|spawn\(/.test(line));
    assert.ok(calls.length > 0, `${relative} should shell out`);
    for (const call of calls) {
      if (/^\s*import\b/.test(call)) continue;
      assert.match(call, /windowsHide: true/, `${relative}: child process must set windowsHide`);
    }
  }
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
  "b-project-structure-survey",
  "b-scenario-product-walkthrough", "b-skill-authoring", "b-source-code-tutoring",
  "b-web-research-tooling", "b-branch-engineering-review", "b-ui-design", "a-workspace-connect", "b-workbench-remote-ops",
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
    // Naming a legacy V1 artifact in order to forbid touching it is not recreating it, so the
    // archive Skill may describe the pre-existing V1 snapshots inside the archive repository.
    const legacyGuard =
      id === "a-project-archive"
        ? /SQLite|event ledger|standalone Evidence/
        : /\.project-log|SQLite|event ledger|standalone Evidence/;
    assert.doesNotMatch(content, legacyGuard, id);
    if (id === "a-project-archive") {
      // The only permitted direction is "leave the existing V1 snapshots alone".
      assert.doesNotMatch(content, /(create|write|append|record)[^.\n]{0,40}\.project-log/i, id);
    }
    assert.doesNotMatch(content, /\.vibe\/requirements\.md/, `${id}: requirement baselines are per work under .vibe/requirements/`);
    assert.match(main, new RegExp("`" + id + "`"), id);
    // File shape is not a measure of engineering ability; see evaluations/README.md.
  }
  assert.ok(existsSync(resolve(root, "skills/b-opencode-model-config/scripts/configure_models.py")));
  assert.ok(existsSync(resolve(root, "skills/b-source-code-tutoring/references/teaching-template.md")));
  assert.doesNotMatch(main, /old Project Log|\.project-log|Goal\/Run\/Evidence\/ledger\/SQLite/, "routing");
});

test("UI design routes are self-contained with one discoverable Skill and no executable assets", () => {
  const base = "skills/b-ui-design";
  const walk = (directory: string): string[] => readdirSync(resolve(root, directory), { withFileTypes: true })
    .flatMap((entry) => entry.isDirectory() ? walk(`${directory}/${entry.name}`) : [`${directory}/${entry.name}`]);
  const files = walk(base);
  assert.deepEqual(files.filter((file) => file.endsWith("/SKILL.md")), [`${base}/SKILL.md`]);
  assert.ok(files.every((file) => /\.(md|json|txt)$|\/LICENSE$/.test(file)), "text-only bundle");
  const router = readNormalized(`${base}/SKILL.md`);
  const guides = ["product-ui", "marketing-ui", "reading-ui", "critique", "interaction", "mobile-web", "resilience", "scenario-reference"];
  for (const guide of guides) assert.ok(router.includes(`guides/${guide}.md`), guide);
  // Active routes never direct the Agent into unresolved upstream workflows.
  assert.doesNotMatch(router, /\]\(sources\//);
  assert.doesNotMatch(router, /current project is a native HTML|hooks:|CLAUDE_PLUGIN_ROOT/);
  for (const file of [`${base}/SKILL.md`, ...guides.map((id) => `${base}/guides/${id}.md`)]) {
    const text = readNormalized(file);
    for (const [, target] of text.matchAll(/\]\(([^)#]+)(?:#[^)]*)?\)/g)) {
      assert.doesNotMatch(target, /^https?:/, `${file}: active methods work offline`);
      assert.ok(existsSync(resolve(root, file, "..", target)), `${file}: ${target}`);
    }
    assert.doesNotMatch(text, /hooks:|\.interface-design\/|\.impeccable\/|CLAUDE_PLUGIN_ROOT|npx skills add/);
  }
  assert.match(readNormalized(`${base}/guides/scenario-reference.md`), /not.*searchable CSV datasets/);
  assert.match(readNormalized(`${base}/EXAMPLES.md`), /manual selection oracles/);
});

test("UI design provenance pins every upstream snapshot, license and notice by digest", () => {
  const base = "skills/b-ui-design";
  const lock = JSON.parse(readNormalized(`${base}/sources.lock.json`));
  assert.equal(lock.format, 1);
  assert.deepEqual(lock.sources.map((s: { id: string }) => s.id).sort(),
    ["emil", "frontend-design", "impeccable", "interface-design", "ui-ux-pro-max"]);
  const recorded = new Set<string>();
  for (const source of lock.sources) {
    assert.match(source.commit, /^[a-f0-9]{40}$/);
    assert.match(source.repository, /^https:\/\/github\.com\/[\w-]+\/[\w-]+$/);
    assert.ok(["MIT", "Apache-2.0"].includes(source.license));
    assert.ok(source.files.some((f: { local: string }) => /\/LICENSE(?:\.txt)?$/.test(f.local)));
    for (const entry of source.files) {
      assert.ok(entry.local.startsWith(`sources/${source.id}/`));
      assert.ok(!entry.local.includes("..") && !entry.upstream.includes(".."));
      assert.ok(!recorded.has(entry.local), entry.local);
      recorded.add(entry.local);
      assert.equal(createHash("sha256").update(readNormalized(`${base}/${entry.local}`)).digest("hex"), entry.sha256, entry.local);
    }
  }
  const walk = (dir: string): string[] => readdirSync(resolve(root, `${base}/${dir}`), { withFileTypes: true })
    .flatMap((entry) => entry.isDirectory() ? walk(`${dir}/${entry.name}`) : [`${dir}/${entry.name}`]);
  assert.deepEqual([...recorded].sort(), walk("sources").sort(), "all snapshots have provenance");
  assert.ok(recorded.has("sources/impeccable/NOTICE.md"));
  const sources = readNormalized(`${base}/SOURCES.md`);
  assert.match(sources, /mixed-license bundle/);
  assert.match(sources, /changed adaptations/);
});

test("every routed Skill is triggerable in the user's language, not only in English", () => {
  // Defect VIBE-FW-ROUTE-001: an English-only trigger row plus an English-only
  // description let a Chinese request ("归档一下") bypass the registered Skill and
  // be answered by an improvised parallel flow.
  const main = readNormalized("runtime/opencode/agents/vibe-main.md");
  const cjk = /[\u4e00-\u9fff]/;
  const routing = main.split("## V2 capability Skill routing")[1];
  assert.ok(routing, "the main Agent must carry the routing table");
  assert.match(routing, /中文别名/, "the routing table must declare Chinese aliases as first-class triggers");
  assert.match(routing, /Hand-rolling an improvised version/, "routing must forbid an improvised substitute");

  for (const id of V2_SKILLS) {
    const row = routing.split("\n").find((line) => line.includes("`" + id + "`"));
    assert.ok(row, `${id} must be routed`);
    const trigger = row.split("|")[1] ?? "";
    assert.match(trigger, cjk, `${id}: the routing trigger needs a Chinese alias`);
    const description = readNormalized(`skills/${id}/SKILL.md`).match(/^description: "(.*)"$/m);
    assert.ok(description, `${id} needs a description`);
    assert.match(description[1], cjk, `${id}: the description must start with Chinese aliases`);
  }
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
