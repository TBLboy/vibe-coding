export const MODES = ["fast", "balanced", "strict"] as const;

export type Mode = (typeof MODES)[number];

export function isMode(value: unknown): value is Mode {
  return typeof value === "string" && (MODES as readonly string[]).includes(value);
}

export function normalizeMode(value: unknown): Mode {
  return isMode(value) ? value : "balanced";
}

export function modeStorageKey(sessionID: string): string {
  if (!sessionID.trim()) throw new Error("sessionID must not be empty");
  return `vibe-v2:session-mode:${sessionID}`;
}

export function pendingModeStorageKey(sessionID: string, token: string): string {
  if (!sessionID.trim() || !token.trim()) throw new Error("sessionID and token must not be empty");
  return `vibe-v2:pending-mode:${sessionID}:${token}`;
}

export interface PendingModeChange {
  mode: Mode;
  token: string;
  consumed: boolean;
}

export function isPendingModeChange(value: unknown, mode: Mode, token: string): value is PendingModeChange {
  if (!value || typeof value !== "object") return false;
  const pending = value as Partial<PendingModeChange>;
  return pending.mode === mode && pending.token === token && pending.consumed === false;
}

/** Build the queued prompt used by explicit native mode commands. */
export function buildModeCommandPrompt(mode: Mode, taskText: string, hasAttachments = false, token = ""): string {
  const task = taskText.trim();
  if (!token.trim()) throw new Error("Mode command token is required");

  const header = [
    `The user explicitly invoked /${mode}. Do not start any work until the mode change tool reports success.`,
    `First call vibe_set_session_mode exactly once with mode=${mode} and token=${token}. If the tool rejects the request, stop and explain that the mode did not change.`,
    "After the tool succeeds, acknowledge briefly; if its result reports a different frozen Task policy, explain it and that the new mode governs new work. Do not imply a paused/closed Task is active or resume it automatically. Closed Tasks cannot resume.",
    "An existing Task keeps the policy captured when that Task started; do not downgrade or upgrade it because the Session mode changed.",
  ].join("\n");

  if (!task && !hasAttachments) {
    return `${header}\nNo task was supplied after the mode command. After the tool succeeds, confirm the mode and any reported frozen-policy distinction only; do not start implementation.`;
  }

  if (!task && hasAttachments) {
    return `${header}\nThe user supplied attachments with the mode command. After the tool succeeds, treat those attachments as the task input and handle them under the selected mode.`;
  }

  const attachmentNote = hasAttachments ? "\n\nThe user also supplied attachments; inspect them if relevant to the request." : "";
  return `${header}\n\nAfter the tool succeeds, execute the following user request under the Session's current mode, unless it is a continuation of an existing Task with a frozen policy:\n\n${task}${attachmentNote}`;
}

export function sessionMemoryRelativePath(sessionID: string): string {
  if (!sessionID.trim()) throw new Error("sessionID must not be empty");
  const segment = encodeURIComponent(sessionID);
  return `.vibe/sessions/${segment}/current-session.md`;
}

export interface SessionContextFacts {
  /** Absolute path of the directory that owns the project's single `.vibe/`. */
  memoryRoot?: string;
  /** The Task currently registered for this Session, if any. */
  activeTask?: { taskID: string; policy: Mode; active: boolean };
}

export function renderModeInstructions(mode: Mode, sessionID?: string, facts: SessionContextFacts = {}): string {
  const relativeRecovery = sessionID ? sessionMemoryRelativePath(sessionID) : ".vibe/sessions/<session-id>/current-session.md";
  const recoveryPath = facts.memoryRoot ? `${facts.memoryRoot}/${relativeRecovery}` : relativeRecovery;
  const memoryRootLine = facts.memoryRoot
    ? `Project memory root: ${facts.memoryRoot} — sole .vibe/ owner, including sub-directories, sub-repositories and worktrees. Never create another .vibe/.`
    : "Project memory root: nearest ancestor owning .vibe/, otherwise project root. Never create another .vibe/ in a sub-directory, sub-repository or worktree.";
  const activeTaskLine = facts.activeTask
    ? `Registered Task for this Session: ${facts.activeTask.taskID} (frozen policy ${facts.activeTask.policy}, ${facts.activeTask.active ? "active" : "paused/closed"}). Read its JSON under .vibe/tasks/ before continuing it; do not register it again.`
    : "No Task is registered for this Session.";
  const shared = [
    "## Vibe Coding V2 — Session Policy",
    `Authoritative Session mode: ${mode}`,
    "For vibe-main only; vibe-reviewer follows its read-only strict review contract, regardless of child Session mode.",
    "Only explicit /fast, /balanced, /strict commands change Session mode; never infer it from text or output. Existing Task policy is frozen and takes precedence for that Task; Session mode applies to new work.",
    memoryRootLine,
    activeTaskLine,
    `Session recovery file: ${recoveryPath}`,
    "Registered Task JSON is Runtime-owned: use vibe_task_control, never edit directly. Verify every code change to its risk floor; explain inapplicable checks and use valid alternatives. Judge risk by consequences, contracts, data/security and recovery, not file count. Stop before strict-risk implementation under fast/balanced policy; require explicit /strict and a new strict Task, not a downgrade.",
    "Ordinary consultation/read-only explanation or investigation without durable tracking needs creates no Task or Reviewer call in any mode; an agreed durable engineering deliverable is not ordinary consultation.",
    "Persist future-useful facts only, not operation logs. Use exact recovery path only for resumable work/blockers; delete it and its empty directory when finished. Update progress only for durable changes.",
  ];
  const newTask: Record<Mode, string> = {
    fast: "Task only for durable tracking/recovery (including persistent acceptance, material decisions/risk, deliverables or blockers); none for trivial work without these needs.",
    balanced: "Task for non-trivial coordination, durable deliverables, persistent acceptance, material risk/decisions, blockers or recovery; not for trivial edits without these needs or file count alone.",
    strict: "For engineering implementation (even small) or engineering work needing durable tracking (including agreed deliverables), create/register a Task via vibe_task_control(action=start) before executing the work; ordinary consultation is excluded.",
  };
  const work: Record<Mode, string> = {
    fast: "Shortest correct path, even for clear multi-file work; skip unnecessary planning/documents, use relevant Skills and risk-appropriate verification. Do not invoke the reviewer or create review records.",
    balanced: "Adapt depth to complexity: direct for simple work, investigate/design/decompose as useful for consequential work; risk-appropriate verification. Do not invoke the reviewer or create review records.",
    strict: "For registered strict work, establish business rules, scope, doneWhen, material decisions and needed breakdown; no mandatory separate documents or Skill sequence. Use begin_verification before checks; submit verification, authorize review, invoke fresh native vibe-reviewer (no reused sessionID). A running result is only a launch: await host notification without polling or duplicate calls. Runtime retrieves verdict on natural parent continuation; read Task then. Do not invent a foreground option or write/forward a verdict. Strict completes only when the reviewer returns go. At most two automatic repairs, each re-verified/re-authorized; block/pause if unresolved or user decision needed. Reviewer assesses agreed scope/evidence only; no edits or scope expansion.",
  };
  // Keep new-work instructions distinct from continuing a frozen Task, including
  // a paused pointer. Never infer that the pointer is a command to resume it.
  const policy = [`New-work policy (${mode}): ${newTask[mode]} ${work[mode]}`];
  if (facts.activeTask && facts.activeTask.policy !== mode) {
    const frozen = facts.activeTask.policy;
    policy.push(`Only if continuing that existing Task, apply frozen policy (${frozen}): ${work[frozen]}`);
  } else if (facts.activeTask) {
    policy.push("Same work rules for continuation; use the existing Task, not new Task creation.");
  }
  return [...shared, ...policy].join("\n");
}
