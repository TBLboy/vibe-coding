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

test("reviewer grants only read and bounded search, not arbitrary investigation commands", () => {
  const reviewer = readNormalized("runtime/opencode/agents/vibe-reviewer.md");
  const front = reviewer.split("---")[1];
  assert.match(front, /mode: subagent/);
  const rules = [...front.matchAll(/  - action: (.*)\n    resource: (.*)\n    effect: (.*)/g)].map(m => ({ action: m[1], resource: m[2], effect: m[3] }));
  assert.deepEqual(rules[0], {action:'"*"',resource:'"*"',effect:'deny'});
  assert.deepEqual(rules.filter(r => r.effect === "allow").map(r => r.action), ["read", "vibe_review_search"]);
  for (const path of ['"**/.env"', '"**/.git/**"', '"**/auth.json"', '"**/credentials.json"']) assert.ok(rules.some(r => r.action === "read" && r.resource === path && r.effect === "deny"));
  assert.match(reviewer, /Investigation may extend beyond changed files/);
  assert.match(reviewer, /green summary alone is insufficient/);
  assert.match(reviewer, /No shell, test execution, network, writes/);
  assert.match(reviewer, /distinguish missing proof from an observed failure/);
  assert.match(reviewer, /do not invent findings/);
});

test("the new pack has no legacy upgrade or migration entrypoints", () => {
  assert.equal(existsSync(resolve(root, "AI_INSTALL.md")), false);
  assert.equal(existsSync(resolve(root, "AI_UPGRADE.md")), false);
  assert.equal(existsSync(resolve(root, "runtime/core/legacy-migration.ts")), false);
});

const V2_SKILLS = [
  "a-architecture-decision", "a-business-clarify", "a-business-code-align",
  "a-codebase-onboarding", "a-deep-research", "a-engineering-landing",
  "a-engineering-spec", "a-paper-reading", "a-project-context-briefing",
  "a-requirement-baseline", "a-retrospective", "a-task-decompose", "a-verification",
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
    const footer = content.split("## V2 operating rules\n");
    assert.equal(footer.length, 2, id);
    assert.equal(footer[1].trim(), "Follow project `AGENTS.md` and effective Policy (frozen policy for existing Task work). Use Runtime lifecycle events, never edit registered Task JSON. Persist only warranted Task/Project Memory facts under the injected root and exact recovery path (`docs/05-MEMORY-CONTRACT.md`). Report evidence and limits; Main Agent owns strict review.", id);
    assert.doesNotMatch(content, /\.project-log|SQLite|event ledger|standalone Evidence/, id);
    assert.doesNotMatch(content, /\.vibe\/requirements\.md/, `${id}: requirement baselines are per work under .vibe/requirements/`);
    assert.match(main, new RegExp("`" + id + "`"), id);
    // File shape is not a measure of engineering ability; see evaluations/README.md.
  }
  assert.ok(existsSync(resolve(root, "skills/b-source-code-tutoring/references/teaching-template.md")));
  assert.doesNotMatch(main, /old Project Log|\.project-log|Goal\/Run\/Evidence\/ledger\/SQLite/, "routing");
});

test("Skill authoring preserves domain value, progressive disclosure and V2 integration boundaries", () => {
  const authoring = readNormalized("skills/b-skill-authoring/SKILL.md");
  assert.match(authoring, /not mandatory headings or a fixed procedure/);
  assert.match(authoring, /## Progressive disclosure/);
  assert.match(authoring, /Keep safety-critical rules here/);
  assert.match(authoring, /explicit named trigger row with its guard/);
  assert.match(authoring, /docs\/05-MEMORY-CONTRACT\.md/);
  assert.match(authoring, /`lessons\/`, and `docs\/`/);
  assert.match(authoring, /Main Agent alone, the previous Skill/);
  assert.match(authoring, /Do not claim better model behavior from structural tests alone/);
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

  const rows = routing.split("\n").filter((line) => /^\| .* \| `[^`]+` \|$/.test(line));
  assert.deepEqual(rows.map((row) => row.split("`")[1]).sort(), [...V2_SKILLS].sort(), "exactly one route per managed Skill");
  for (const id of V2_SKILLS) {
    const row = rows.find((line) => line.includes("`" + id + "`"));
    assert.ok(row, `${id} must be routed`);
    const trigger = row.split("|")[1] ?? "";
    assert.match(trigger, cjk, `${id}: the routing trigger needs a Chinese alias`);
    const description = readNormalized(`skills/${id}/SKILL.md`).match(/^description: "(.*)"$/m);
    assert.ok(description, `${id} needs a description`);
    assert.match(description[1].split("|")[0], cjk, `${id}: the description must lead with Chinese aliases`);
  }
  // These historically important distinctions must survive route compression.
  const route = (id: string) => rows.find((line) => line.includes("`" + id + "`"))!;
  assert.match(route("b-web-research-tooling"), /网络资料搜索.*not broad decision research/);
  assert.match(route("a-engineering-landing"), /not trivial edits/);
  assert.match(route("a-verification"), /not routine test runs/);
  assert.match(route("b-branch-engineering-review"), /explicitly named branch/);
  assert.match(route("b-workbench-remote-ops"), /explicit requests only/);
  assert.match(route("a-workspace-connect"), /本地初始化.*离线初始化/);
  assert.match(readNormalized("skills/a-workspace-connect/SKILL.md").split("\n")[2], /本地初始化.*离线初始化/);
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

const RETIRED_SKILLS = ["a-project-archive", "b-multi-role-ux-audit", "b-concise-communication", "b-plan-stress-test", "b-jetson-robot-policy-deployment", "b-opencode-model-config"];

test("retired capabilities are absent from active Skills, routes and executable test entrypoints", () => {
  const main = readNormalized("runtime/opencode/agents/vibe-main.md");
  const pkg = readNormalized("package.json");
  const activeMarkdown = (dir: string): string[] => readdirSync(resolve(root, dir), {withFileTypes: true})
    .flatMap(entry => entry.isDirectory() && entry.name !== "sources" ? activeMarkdown(`${dir}/${entry.name}`)
      : entry.isFile() && entry.name.endsWith(".md") ? [`${dir}/${entry.name}`] : []);
  assert.equal(V2_SKILLS.length, 22);
  for (const id of RETIRED_SKILLS) {
    assert.ok(!existsSync(resolve(root, "skills", id)), id);
    assert.ok(!main.includes(id), id);
    for (const file of activeMarkdown("skills")) assert.ok(!readNormalized(file).includes(id), `${file}: ${id}`);
  }
  for (const helper of ["test_v2_project_archive.py", "test_v2_configure_models.py"]) {
    assert.ok(!existsSync(resolve(root, "scripts", helper)));
    assert.ok(!pkg.includes(helper));
  }
  assert.match(main, /every user-facing message concise, direct, efficient and focused/);
  assert.match(main, /preserve necessary evidence, warnings and requested detail/);
});

test("online search remains focused and evidence-grounded without a new research workflow", () => {
  const search = readNormalized("skills/b-web-research-tooling/SKILL.md");
  assert.match(search, /a-deep-research` owns decision-oriented synthesis/);
  assert.match(search, /snippets are leads, not proof/);
  assert.match(search, /match the actual version/);
  assert.match(search, /independent evidence/);
  assert.match(search, /untrusted data, not instructions/);
  assert.match(search, /do not invent sources, excerpts, URLs/);
  assert.match(search, /No mandatory source table or durable record/);
});

// Structural regression guards for the eight refined engineering methods. These
// assert the instruction contract, not model compliance or engineering ability.
test("core engineering Skills preserve authority and real Task lifecycle", () => {
  const body = (id: string) => readNormalized(`skills/${id}/SKILL.md`);
  const contract = readNormalized("docs/06-AGENT-CONTRACT.md");
  assert.match(contract, /no event that rewrites registered criteria/);
  assert.match(contract, /cancel and close superseded non-terminal work/);
  for (const id of ["a-business-clarify", "a-requirement-baseline"]) {
    assert.match(body(id), /before registration/i);
    assert.match(body(id), /supersession rule in `docs\/06-AGENT-CONTRACT\.md`/);
    assert.doesNotMatch(body(id), /update the Task `goal`\s*\/\s*`doneWhen`/);
  }
  assert.match(body("a-business-code-align"), /audit-only request authorizes investigation and findings, not repairs/);
  assert.match(body("a-business-code-align"), /only when implementation is authorized/);
  assert.match(body("a-task-decompose"), /Do not pre-create registered-looking Task JSON/);
  assert.match(body("a-task-decompose"), /vibe_task_control\(action=start\)/);
  assert.match(body("a-task-decompose"), /One registered active Task per Session/);
});

test("core engineering Skills keep distinct domain methods and linked examples", () => {
  const body = (id: string) => readNormalized(`skills/${id}/SKILL.md`);
  assert.match(body("a-architecture-decision"), /mutable state\/invariant an identifiable owner/);
  assert.match(body("a-architecture-decision"), /static dependencies separately from runtime data flow/);
  assert.match(body("a-engineering-spec"), /not thirteen mandatory sections/);
  assert.match(body("a-engineering-landing"), /Every removed responsibility needs a replacement or authorized retirement/);
  assert.match(body("a-verification"), /Independent oracle/);
  assert.match(body("a-verification"), /before final checks/);
  assert.match(body("a-verification"), /Essential unverified criteria require `verification_failed` or `block`/);
  for (const [id, ref] of [["a-architecture-decision", "decision-method.md"], ["a-engineering-landing", "change-method.md"], ["a-verification", "test-design.md"]]) {
    assert.ok(body(id).includes(`references/${ref}`), id);
    assert.ok(existsSync(resolve(root, "skills", id, "references", ref)), id);
  }
});

// Cognition Skill guards pin boundaries and professional method cues, not model behavior.
test("engineering cognition Skills distinguish source evidence, static maps and illustrative behavior", () => {
  const body = (id: string) => readNormalized(`skills/${id}/SKILL.md`);
  const onboarding = body("a-codebase-onboarding");
  assert.match(onboarding, /available code from enabled code/);
  assert.match(onboarding, /not automatically business authority/);
  assert.match(onboarding, /keep any proposed baseline `draft` until authorized/);
  assert.match(onboarding, /require user approval before editing it/);
  const survey = body("b-project-structure-survey");
  assert.match(survey, /A static import graph is not a runtime call graph or change-impact graph/);
  assert.match(survey, /no repository or Project Memory writes/);
  assert.match(survey, /not project execution, builds, tests or installation/);
  const tutoring = body("b-source-code-tutoring");
  assert.match(tutoring, /routing: explicit-only/);
  assert.match(tutoring, /initial value, writers, readers, effect, terminal\/reset/);
  assert.match(tutoring, /cover every requested line/);
  assert.match(tutoring, /static path, actual observed trace and unverified downstream behavior/);
  assert.match(tutoring, /references\/teaching-template\.md/);
  const walkthrough = body("b-scenario-product-walkthrough");
  assert.match(walkthrough, /user intent\/action → system response → visible result\/artifact\/state → control boundary/);
  assert.match(walkthrough, /not force irrelevant branches/);
  assert.match(walkthrough, /Do not treat the example as an approved requirement/);
});

test("knowledge Skills preserve research evidence, privacy and Runtime-owned memory boundaries", () => {
  const body = (id: string) => readNormalized(`skills/${id}/SKILL.md`);
  const research = body("a-deep-research");
  assert.match(research, /current\/no-change where credible/);
  assert.match(research, /hard disqualifiers from preferences/);
  assert.match(research, /conditions that would reverse the recommendation/);
  assert.match(research, /b-web-research-tooling/);
  const paper = body("a-paper-reading");
  for (const level of [0, 1, 2, 3, 4]) assert.match(paper, new RegExp(`L${level} —`));
  assert.match(paper, /dataset split\/leakage risk/);
  assert.match(paper, /A plan is not a reproduced result/);
  assert.match(paper, /claim → assumptions → method → evidence → limitations/);
  for (const id of ["a-deep-research", "a-paper-reading", "a-project-context-briefing"]) {
    assert.match(body(id), /`record_decision` in prepare\/implement/);
    assert.doesNotMatch(body(id), /in the active Task JSON `decisions`|from the Task `nextAction`/);
  }
  const brief = body("a-project-context-briefing");
  assert.match(brief, /Do not send, post, upload or change visibility without explicit authorization/);
  assert.match(brief, /Do not directly edit registered `nextAction`/);
  const retro = body("a-retrospective");
  assert.match(retro, /immediate trigger, causal mechanism and contributing conditions/);
  assert.match(retro, /\.vibe\/lessons\/<id>\.md` and its index/);
  assert.match(retro, /at three occurrences propose distillation into `AGENTS\.md`, never edit it without user approval/);
  assert.match(retro, /retrospective alone does not authorize/);
});


test("specialist review and UI Skills preserve scope and evidence boundaries", () => {
  const body = (id: string) => readNormalized(`skills/${id}/SKILL.md`);
  const branch = body("b-branch-engineering-review");
  for (const pair of ["B → F", "B → T", "T → M", "F → M"]) assert.ok(branch.includes(pair));
  assert.match(branch, /git merge-base --all/);
  assert.match(branch, /git write-tree/);
  assert.match(branch, /HEAD` still denotes T, not M/);
  assert.match(branch, /merge_result_tree/);
  assert.match(branch, /Do not\nuse `-X ours` as evidence/);
  assert.match(branch, /Remove only the review-created worktree/);
  assert.match(branch, /Never return a merge verdict/);
  const ui = body("b-ui-design");
  assert.match(ui, /## Design judgment/);
  assert.match(ui, /one primary guide/);
  assert.match(ui, /same viewport, content and state before\/after/);
  assert.match(ui, /Never claim a full accessibility audit from sampled checks/);
  assert.doesNotMatch(readNormalized("skills/b-ui-design/guides/critique.md"), /dedicated audit capability/);
  assert.match(readNormalized("skills/b-ui-design/guides/scenario-reference.md"), /2\.5\.8: 24 CSS px or applicable exception/);
});

test("workspace specialist instructions match connection outcomes and admin authorization", () => {
  const connect = readNormalized("skills/a-workspace-connect/SKILL.md");
  assert.match(connect, /Never infer that two Keys reach the same workspace/);
  assert.match(connect, /Binding success does not prove first sync success/);
  assert.match(connect, /It binds only/);
  assert.match(connect, /cloud_changed/);
  assert.match(connect, /not necessarily the latest local edit/);
  assert.match(connect, /different identity does not\ninherit it/);
  const ops = readNormalized("skills/b-workbench-remote-ops/SKILL.md");
  assert.match(ops, /Use verified HTTPS for public credentials/);
  assert.match(ops, /Both\ncreation routes lack idempotency keys/);
  assert.match(ops, /Key rotation is not exposed by the current public API/);
  assert.match(ops, /requires that workspace's Key, not the administrator token/);
  assert.match(ops, /verify deployed\ncommit separately/);
  assert.match(ops, /Restore only with user approval/);
  assert.match(ops, /Read-only inspection does not authorize/);
  const integration = readNormalized("docs/08-OPENCODE-INTEGRATION.md");
  assert.match(integration, /generated canonical engineering-dev template for explicit offline initialization/);
  assert.doesNotMatch(integration, /local package ships no project-initialization templates/);
});


test("Project Memory instructions preserve quality, claim-specific authority and selective retrieval", () => {
  const contract = readNormalized("docs/05-MEMORY-CONTRACT.md");
  const main = readNormalized("runtime/opencode/agents/vibe-main.md");
  assert.match(contract, /accurate, independently understandable, causal where relevant, scoped, traceable and concise/);
  assert.match(contract, /one authoritative home per fact/);
  assert.match(contract, /Use authority by claim, not a blanket file ranking/);
  assert.match(contract, /open only useful source records/);
  assert.match(contract, /never guess by timestamps or read\/write another Session's recovery directory/);
  assert.match(contract, /At 3 occurrences[\s\S]*earlier proposal[\s\S]*never edits `AGENTS\.md` without the user's decision/);
  assert.match(contract, /never overlay, migrate or rewrite existing memory on upgrade or import/);
  assert.match(main, /docs\/05-MEMORY-CONTRACT\.md/);
  assert.match(main, /No bulk memory injection/);
  assert.match(main, /edit `AGENTS\.md` only with user approval/);
  assert.match(main, /Keep progress current, not append-only/);
  assert.match(main, /delete it and its empty directory when no longer needed/);
  const body = (id: string) => readNormalized(`skills/${id}/SKILL.md`);
  assert.match(body("a-retrospective"), /Count distinct incidents, not mentions/);
  assert.match(body("a-codebase-onboarding"), /selectively follow relevant technical docs and lessons/);
  assert.match(body("a-requirement-baseline"), /keep the prior baseline and supersession links/);
  assert.match(body("a-architecture-decision"), /not a second decision ledger/);
  assert.match(body("a-engineering-landing"), /reconcile the affected current technical knowledge/);
  assert.match(body("a-verification"), /rather than reusing old test results/);
});

// Structural contract only: real model economy and recovery need host trials.
test("context guidance protects evidence, native recovery and strict handoff", () => {
  const main = readNormalized("runtime/opencode/agents/vibe-main.md");
  const agent = readNormalized("docs/06-AGENT-CONTRACT.md");
  const integration = readNormalized("docs/08-OPENCODE-INTEGRATION.md");
  const memory = readNormalized("docs/05-MEMORY-CONTRACT.md");
  assert.match(main, /Locate before reading/);
  assert.match(main, /Avoid bulk reads and repeated Skill\/reference loads/);
  assert.match(main, /preserve exit status, failures, diagnostics and evidence/);
  assert.match(main, /Never infer completion from a summary or resume another Session/);
  assert.match(main, /complete in-scope diff or precise changed-file evidence/);
  assert.match(agent, /A filtered or truncated output is not a pass/);
  assert.match(agent, /Do not split a single review into unofficial partial verdicts/);
  assert.match(integration, /this package sets no compaction\/model\/provider configuration/);
  assert.match(integration, /A compacted reviewer child is not an accepted verdict/);
  assert.match(memory, /A summary is navigation, not authority or proof of completion/);
  assert.match(readNormalized("skills/b-ui-design/SKILL.md"), /No guide delegates to another Agent/);
  const config = JSON.parse(readNormalized("runtime/opencode/opencode.json"));
  assert.equal(config.compaction, undefined);
});

// Structural consistency, not evidence of real-model workflow behavior.
test("mode experience keeps strict execution gates and ordinary consultation boundary aligned", () => {
  const main = readNormalized("runtime/opencode/agents/vibe-main.md");
  const product = readNormalized("docs/01-PRODUCT-CONTRACT.md");
  const agent = readNormalized("docs/06-AGENT-CONTRACT.md");
  assert.match(main, /No Task\/Reviewer for ordinary consultation/);
  assert.match(main, /Strict engineering implementation \(even small\)/);
  assert.match(product, /Do not recast actual implementation as consultation to bypass strict review/);
  assert.match(product, /A Task cannot complete until the reviewer returns `go`/);
  assert.match(product, /File count alone is not a persistence signal/);
  assert.match(agent, /not invoked to classify user messages by Runtime/);
  assert.match(readNormalized("skills/a-engineering-landing/SKILL.md"), /Register strict implementation before edits, even for small changes/);
  assert.match(readNormalized("skills/a-verification/SKILL.md"), /All registered strict Tasks require review even for quick work/);
});
