import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, realpath, rename, unlink, writeFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
import { fingerprintArtifacts, evidenceCurrent } from "../../../core/artifact-evidence.ts";
import { createTask, transitionTask, type Task, type TaskEvent, type ReviewFinding } from "../../../core/task-machine.ts";
import { validateTaskRecord } from "../../../core/task-record.ts";
import { normalizeMode, modeStorageKey } from "../../../core/mode.ts";
import { activeTaskStorageKey, isTaskPointer } from "../../../core/review-authorization.ts";

export interface ControlStorage { get(key: string): Promise<unknown>; set(key: string, value: unknown): Promise<void>; remove(key: string): Promise<void> }
export interface ControlHost {
  storage: ControlStorage;
  memoryRoot(sessionID: string): Promise<string | null>;
  workspace(sessionID: string): Promise<string | null>;
  childSession(sessionID: string): Promise<{ parentID?: string; agent?: string; outcome?: string }>;
  childContext(sessionID: string): Promise<readonly unknown[]>;
  /** Hash recorded by the sync manifest for a synced path, or null when the path is not tracked. Required for adopt. */
  syncedHash?(root: string, path: string): Promise<string | null>;
}
export interface Caller { sessionID: string; agent?: string }
export interface ReviewCall { messageID: string; id: string }
interface Receipt { owner: string; policy: Task["policy"]; digest: string; closed: boolean; review?: { digest: string; call?: ReviewCall; childSessionID?: string } }
const hash = (s: string) => createHash("sha256").update(s).digest("hex");
const idPattern = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const locks = new Map<string, Promise<void>>();
async function serial<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const previous = locks.get(key) ?? Promise.resolve();
  let release!: () => void;
  const pending = new Promise<void>(r => { release = r; });
  const tail = previous.then(() => pending);
  locks.set(key, tail);
  await previous;
  try { return await fn(); } finally { release(); if (locks.get(key) === tail) locks.delete(key); }
}
const object = (x: unknown): Record<string, unknown> => {
  if (!x || typeof x !== "object" || Array.isArray(x)) throw new Error("Expected an object");
  return x as Record<string, unknown>;
};
const string = (x: unknown): string => { if (typeof x !== "string" || !x.trim()) throw new Error("Expected a nonempty string"); return x; };
const strings = (x: unknown): string[] => { if (!Array.isArray(x) || x.some(v => typeof v !== "string")) throw new Error("Expected a string array"); return x; };
const optionalString = (x: unknown) => x === undefined ? undefined : string(x);
const optionalStrings = (x: unknown) => x === undefined ? undefined : strings(x);
function parseFindings(x: unknown): ReviewFinding[] {
  if (!Array.isArray(x)) throw new Error("Expected findings array");
  return x.map(v => { const f = object(v); if (f.severity !== "critical" && f.severity !== "major" && f.severity !== "minor") throw new Error("Invalid finding severity"); return { severity: f.severity, requirement: string(f.requirement), location: string(f.location), problem: string(f.problem), requiredChange: string(f.requiredChange) }; });
}

function verdictEvent(text: string): TaskEvent | null {
  // Accept an exact JSON object or one JSON code fence, never a substring or
  // parent-authored notification text.
  const trimmed = text.trim();
  const fenced = trimmed.match(/^```(?:json)?\s*\n([\s\S]*?)\n```$/i);
  const record = object(JSON.parse(fenced ? fenced[1] : trimmed));
  const findings = parseFindings(record.findings);
  if (typeof record.requiresUserDecision !== "boolean") return null;
  if (record.verdict === "go" && findings.length === 0 && !record.requiresUserDecision) return { type: "review_go" };
  if ((record.verdict === "conditional" || record.verdict === "no-go") && findings.length) {
    return { type: "review_changes_required", verdict: record.verdict, findings, requiresUserDecision: record.requiresUserDecision };
  }
  return null;
}

/** Only the first un-compacted successful turn of a fresh child is usable.
 * Later prompts, compaction summaries, reasoning and intermediate text are not verdicts. */
function terminalReviewerText(messages: readonly unknown[]): string | null {
  const records = messages.map(object);
  if (records.filter(m => m.type === "user").length !== 1 || records.filter(m => m.type === "idle").length !== 1) return null;
  if (records.some(m => ["compaction", "synthetic", "agent-switched"].includes(String(m.type)))) return null;
  const idle = records.at(-1), assistant = records.at(-2);
  if (idle?.type !== "idle" || idle.outcome !== "succeeded" || idle.error !== undefined) return null;
  if (assistant?.type !== "assistant" || assistant.agent !== "vibe-reviewer" || assistant.finish !== "stop" || assistant.error !== undefined) return null;
  const time = object(assistant.time);
  if (time.completed === undefined || time.completed === null || !Array.isArray(assistant.content)) return null;
  // Unsettled steps cannot be a completed review. A tool error that the reviewer
  // recovered from is not by itself a failed child execution.
  for (const message of records.filter(m => m.type === "assistant")) {
    if (message.agent !== "vibe-reviewer" || message.error !== undefined || object(message.time).completed === undefined) return null;
    if (!Array.isArray(message.content)) return null;
    for (const part of message.content.map(object)) {
      if (part.type === "tool" && !["completed", "error"].includes(String(object(part.state).status))) return null;
    }
  }
  const parts = assistant.content.map(object);
  if (parts.some(p => p.type === "tool")) return null;
  const text = parts.filter(p => p.type === "text").map(p => string(p.text)).join("");
  return text || null;
}

/** Runtime-owned lifecycle. The persisted Task remains the human-readable source;
 * plugin storage keeps only a project-scoped integrity/ownership receipt, not a second Task. */
export function createTaskController(host: ControlHost) {
  const storage = host.storage;
  async function location(sessionID: string, taskID: string) {
    if (!idPattern.test(taskID)) throw new Error("Invalid Task ID");
    const root = await host.memoryRoot(sessionID);
    if (!root) throw new Error("Project memory root unavailable");
    const key = `vibe-v2:task-receipt:${hash(root)}:${taskID}`;
    const base = resolve(root, ".vibe");
    if (await realpath(base) !== base) throw new Error("Unsafe .vibe root");
    const dir = resolve(base, "tasks");
    await mkdir(dir, { recursive: true });
    if (await realpath(dir) !== dir) throw new Error("Unsafe Task directory");
    return { root, key, path: resolve(dir, `${taskID}.json`) };
  }
  type Location = Awaited<ReturnType<typeof location>>;
  async function load(loc: Location, taskID: string) {
    if (await realpath(loc.path) !== loc.path) throw new Error("Unsafe Task file");
    const raw = await readFile(loc.path, "utf8");
    const value = JSON.parse(raw) as Task;
    const problems = validateTaskRecord(value, taskID);
    if (problems.length) throw new Error(problems.join("; "));
    return { task: value, digest: hash(raw) };
  }
  async function save(loc: Location, task: Task, receipt: Receipt) {
    const problems = validateTaskRecord(task, task.id);
    if (problems.length) throw new Error(problems.join("; "));
    const raw = JSON.stringify(task, null, 2) + "\n";
    const tmp = `${loc.path}.${randomUUID()}.tmp`;
    try { await writeFile(tmp, raw, { flag: "wx", mode: 0o600 }); await rename(tmp, loc.path); }
    finally { await unlink(tmp).catch(() => {}); }
    // If the storage write fails after rename, next call rejects the mismatched receipt.
    await storage.set(loc.key, { ...receipt, digest: hash(raw) });
  }
  async function registered(loc: Location, taskID: string) {
    const receipt = await storage.get(loc.key) as Receipt | undefined;
    if (!receipt) throw new Error("Unregistered/legacy Task: preserve the original, start a new Task ID and re-verify; no automatic trust import");
    const { task, digest } = await load(loc, taskID);
    if (receipt.digest !== digest || receipt.policy !== task.policy) throw new Error("Task was changed outside Runtime; restore the last registered record or start a new Task");
    return { task, receipt };
  }
  async function current(task: Task, sessionID: string) {
    const evidence = task.verification.evidence;
    const workspace = await host.workspace(sessionID);
    return Boolean(evidence && workspace && evidence.root === workspace && await evidenceCurrent(evidence));
  }
  async function pointer(sessionID: string, task: Task, active: boolean) {
    await storage.set(activeTaskStorageKey(sessionID), { taskID: task.id, policy: task.policy, active });
  }
  async function ensureNoOther(sessionID: string, taskID: string) {
    const p = await storage.get(activeTaskStorageKey(sessionID));
    if (isTaskPointer(p) && p.active && p.taskID !== taskID) throw new Error(`Task ${p.taskID} is already active`);
  }
  async function control(input: Record<string, unknown>, caller: Caller): Promise<string> {
    if (caller.agent !== "vibe-main") throw new Error("Only vibe-main can control Tasks");
    const taskID = string(input.taskID), action = string(input.action);
    const loc = await location(caller.sessionID, taskID);
    return serial(loc.root, async () => {
      const sessionID = caller.sessionID;
      await ensureNoOther(sessionID, taskID);
      if (action === "start") {
        if (await storage.get(loc.key)) throw new Error("Task ID is already registered; use resume");
        const { task } = await load(loc, taskID);
        const mode = normalizeMode(await storage.get(modeStorageKey(sessionID)));
        const fresh = createTask({ id: task.id, title: task.title, goal: task.goal, doneWhen: task.doneWhen, policy: mode });
        if (task.policy !== mode || task.status !== "active" || task.phase !== "prepare" || task.verification.status !== "not_run" || task.review || task.decisions.length) throw new Error("New Task must be a fresh prepare record matching Session mode");
        await save(loc, fresh, { owner: sessionID, policy: mode, digest: "", closed: false });
        await pointer(sessionID, fresh, true);
        return `Task ${taskID} started in prepare.`;
      }
      if (action === "adopt") {
        // Cross-device continuation: a Task file delivered by sync is the authoritative record. Take it over only when it is intact
        // (matches the sync manifest hash, passes schema) and not terminal; old evidence and review permits are void.
        if (!host.syncedHash) throw new Error("Task adoption is unavailable: sync manifest is not connected");
        const prior = await storage.get(loc.key) as Receipt | undefined;
        if (prior?.closed) throw new Error("Task is closed; start a new Task");
        const { task: synced, digest } = await load(loc, taskID);
        if (await host.syncedHash(loc.root, `.vibe/tasks/${taskID}.json`) !== digest) throw new Error("Task file does not match the synced version; sync first or start a new Task");
        if (synced.status === "completed" || synced.status === "cancelled") throw new Error("Terminal Tasks cannot be adopted");
        const adopted: Task = {
          ...synced,
          phase: synced.phase === "prepare" ? "prepare" : "implement",
          verification: { status: "not_run", summary: "", checks: [], limitations: [] },
          review: synced.review ? { ...synced.review, verdict: "pending", findings: [] } : undefined,
          nextAction: synced.nextAction ?? "Adopted from another device: re-run implementation checks and verify again.",
        };
        if (prior && prior.owner !== sessionID) { const old = await storage.get(activeTaskStorageKey(prior.owner)); if (isTaskPointer(old, taskID)) await pointer(prior.owner, adopted, false); }
        await save(loc, adopted, { owner: sessionID, policy: adopted.policy, digest: "", closed: false });
        await pointer(sessionID, adopted, true);
        return `Task ${taskID} adopted with frozen policy ${adopted.policy}; verification and review must be redone.`;
      }
      let { task, receipt } = await registered(loc, taskID);
      if (receipt.closed) throw new Error("Task is closed; start a new Task");
      if (action === "resume") {
        if (task.status === "blocked") throw new Error("Use resume_blocked with a recorded decision when required");
        if (task.status !== "active" && task.status !== "completed" && task.status !== "cancelled") throw new Error("Task cannot resume");
        // Reclaim after interruption, preserving frozen policy. Any old owner loses authority.
        if (receipt.owner !== sessionID) { const old = await storage.get(activeTaskStorageKey(receipt.owner)); if (isTaskPointer(old, taskID)) await pointer(receipt.owner, task, false); }
        receipt = { ...receipt, owner: sessionID, review: undefined };
        await storage.set(loc.key, JSON.parse(JSON.stringify(receipt)));
        await pointer(sessionID, task, true);
        return `Task ${taskID} resumed with frozen policy ${task.policy}.`;
      }
      if (action === "resume_blocked") {
        if (task.status !== "blocked") throw new Error("Only blocked Tasks can resume_blocked");
        const e = object(input.event ?? {});
        const phase = e.phase;
        if (phase !== undefined && !["prepare", "implement", "verify", "review"].includes(String(phase))) throw new Error("Invalid resume phase");
        if (task.phase === "review" && task.review?.verdict !== "pending" && phase !== "implement") throw new Error("Resolve reviewer findings by resuming into implementation with a recorded decision");
        task = transitionTask(task, { type: "resume", phase: phase as Task["phase"] | undefined, decision: optionalString(e.decision), nextAction: optionalString(e.nextAction) });
        if (receipt.owner !== sessionID) { const old = await storage.get(activeTaskStorageKey(receipt.owner)); if (isTaskPointer(old, taskID)) await pointer(receipt.owner, task, false); }
        receipt = { owner: sessionID, policy: task.policy, digest: "", closed: false };
        await save(loc, task, receipt); await pointer(sessionID, task, true);
        return `Task ${taskID} resumed from blocker.`;
      }
      const p = await storage.get(activeTaskStorageKey(sessionID));
      if (receipt.owner !== sessionID || !isTaskPointer(p, taskID) || !p.active) throw new Error("Task is not active in this Session; resume first");
      if (action === "pause") {
        if (task.status !== "blocked") throw new Error("Only blocked Tasks may pause");
        delete receipt.review; await storage.set(loc.key, receipt); await pointer(sessionID, task, false);
        return `Task ${taskID} paused.`;
      }
      if (action === "close") {
        if (task.status !== "cancelled" && (task.status !== "completed" || !await current(task, sessionID) || (task.policy === "strict" && task.review?.verdict !== "go"))) throw new Error("Completion requires current verification and, for strict, a reviewer go; invalidate stale evidence and re-verify");
        await storage.set(loc.key, { owner: sessionID, policy: task.policy, digest: receipt.digest, closed: true });
        await pointer(sessionID, task, false);
        return `Task ${taskID} closed.`;
      }
      if (action === "authorize_review") {
        if (task.policy !== "strict" || task.phase !== "review" || task.status !== "active" || task.review?.verdict !== "pending" || !await current(task, sessionID)) throw new Error("Review requires active strict Task with current verification and pending verdict");
        if (receipt.review) throw new Error("Review already authorized; use reset_review if the call failed or was interrupted");
        await storage.set(loc.key, { ...receipt, review: { digest: receipt.digest } });
        return `Reviewer permit issued for ${taskID}. Invoke a fresh native vibe-reviewer with the current Task and diff; omit sessionID. A running result is only a launch: wait for the host notification without polling. Runtime reads the child's terminal verdict at the next natural parent continuation. Never submit or copy a verdict yourself.`;
      }
      if (action === "reset_review") {
        if (task.phase !== "review" || task.review?.verdict !== "pending") throw new Error("No pending review");
        delete receipt.review; await storage.set(loc.key, receipt); return "Pending review invalidated; authorize a new round.";
      }
      if (action !== "transition") throw new Error("Unknown Task action");
      const e = object(input.event);
      let event: TaskEvent;
      switch (e.type) {
        case "begin_implementation": {
          const risk = string(e.risk);
          if (!["quick", "standard", "strict"].includes(risk)) throw new Error("Invalid engineering risk");
          if (risk === "strict" && task.policy !== "strict") throw new Error("Strict risk requires an explicit /strict and new strict Task; do not downgrade risk");
          event = { type: e.type }; break;
        }
        case "begin_verification": {
          const workspace = await host.workspace(sessionID);
          if (!workspace) throw new Error("Workspace unavailable");
          event = { type: e.type, evidence: await fingerprintArtifacts(workspace, strings(e.artifacts)) }; break;
        }
        case "verification_passed": {
          if (!await current(task, sessionID)) throw new Error("Artifact evidence changed or missing; invalidate verification and re-run checks");
          if (e.status !== undefined && e.status !== "passed" && e.status !== "not_applicable") throw new Error("Invalid verification status");
          event = { type: e.type, status: e.status, summary: string(e.summary), checks: optionalStrings(e.checks), limitations: optionalStrings(e.limitations), notApplicableReason: optionalString(e.notApplicableReason) }; break;
        }
        case "verification_failed": event = { type: e.type, summary: string(e.summary), checks: optionalStrings(e.checks), limitations: optionalStrings(e.limitations) }; break;
        case "invalidate_verification": event = { type: e.type }; break;
        case "record_decision": event = { type: e.type, decision: string(e.decision) }; break;
        case "block": case "cancel": event = { type: e.type, reason: string(e.reason) }; break;
        default: throw new Error("Unknown or reviewer-only transition");
      }
      task = transitionTask(task, event);
      await save(loc, task, { owner: sessionID, policy: task.policy, digest: "", closed: false });
      return `Task ${taskID}: ${task.status}/${task.phase}.`;
    });
  }
  async function admit(sessionID: string, agent: string | undefined, call: ReviewCall | undefined): Promise<boolean> {
    if (agent !== "vibe-main" || !call?.messageID || !call.id) return false;
    const p = await storage.get(activeTaskStorageKey(sessionID));
    if (!isTaskPointer(p) || !p.active || p.policy !== "strict") return false;
    const loc = await location(sessionID, p.taskID);
    return serial(loc.root, async () => {
      const { task, receipt } = await registered(loc, p.taskID);
      if (receipt.owner !== sessionID || receipt.closed || !receipt.review || receipt.review.call || receipt.review.digest !== receipt.digest || task.phase !== "review" || task.status !== "active" || !await current(task, sessionID)) return false;
      await storage.set(loc.key, { ...receipt, review: { ...receipt.review, call } });
      return true;
    });
  }
  /** Observe a native launch/completion. Admission and status running are not verdicts.
    * The main Agent cannot submit a verdict through a custom tool. */
  async function complete(parent: string, agent: string, call: ReviewCall, input: unknown, output: unknown): Promise<boolean> {
    if (agent !== "vibe-main") return false;
    const p = await storage.get(activeTaskStorageKey(parent));
    if (!isTaskPointer(p) || !p.active || p.policy !== "strict") return false;
    const loc = await location(parent, p.taskID);
    return serial(loc.root, async () => {
      const { task, receipt } = await registered(loc, p.taskID);
      const expected = receipt.review?.call;
      if (receipt.owner !== parent || receipt.closed || !expected || expected.id !== call.id || expected.messageID !== call.messageID || receipt.review?.digest !== receipt.digest || task.phase !== "review" || task.status !== "active" || !await current(task, parent)) return false;
      const request = object(input), result = object(output);
      if (request.agent !== "vibe-reviewer" || request.sessionID !== undefined || typeof result.sessionID !== "string" || !result.sessionID) return false;
      // A duplicate launch cannot replace the bound child or inject a completed result.
      if (receipt.review?.childSessionID) return false;
      const child = await host.childSession(result.sessionID);
      if (child.parentID !== parent || child.agent !== "vibe-reviewer" || await host.workspace(result.sessionID) !== await host.workspace(parent)) return false;
      if (result.status === "running") {
        if (!await current(task, parent)) return false;
        await storage.set(loc.key, { ...receipt, review: { ...receipt.review!, childSessionID: result.sessionID } });
        return false;
      }
      // Preserve the older synchronous native contract; a background launch must
      // use the separate host-owned child transcript path below.
      if (request.background === true || result.status !== "completed" || typeof result.output !== "string") return false;
      const event = verdictEvent(result.output);
      if (!event || !await current(task, parent)) return false;
      const next = transitionTask(task, event);
      await save(loc, next, { owner: parent, policy: task.policy, digest: "", closed: false });
      return true;
    });
  }

  /** Called only on a natural parent context continuation (including the host's
   * background completion notice), not by an Agent completion tool or timer. */
  async function reconcile(parent: string): Promise<boolean> {
    const p = await storage.get(activeTaskStorageKey(parent));
    if (!isTaskPointer(p) || !p.active || p.policy !== "strict") return false;
    const loc = await location(parent, p.taskID);
    return serial(loc.root, async () => {
      const { task, receipt } = await registered(loc, p.taskID);
      const review = receipt.review;
      if (receipt.owner !== parent || receipt.closed || !review?.call || !review.childSessionID || review.digest !== receipt.digest || task.phase !== "review" || task.status !== "active" || !await current(task, parent)) return false;
      const child = await host.childSession(review.childSessionID);
      if (child.parentID !== parent || child.agent !== "vibe-reviewer" || child.outcome !== "succeeded" || await host.workspace(review.childSessionID) !== await host.workspace(parent)) return false;
      const text = terminalReviewerText(await host.childContext(review.childSessionID));
      if (text === null) return false;
      const event = verdictEvent(text);
      const settledChild = await host.childSession(review.childSessionID);
      if (!event || settledChild.parentID !== parent || settledChild.agent !== "vibe-reviewer" || settledChild.outcome !== "succeeded" || await host.workspace(review.childSessionID) !== await host.workspace(parent) || !await current(task, parent)) return false;
      const next = transitionTask(task, event);
      await save(loc, next, { owner: parent, policy: task.policy, digest: "", closed: false });
      return true;
    });
  }
  return { control, admit, complete, reconcile };
}
