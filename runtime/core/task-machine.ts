import type { Mode } from "./mode.ts";

export type TaskStatus = "active" | "blocked" | "completed" | "cancelled";
export type TaskPhase = "prepare" | "implement" | "verify" | "review" | "complete";
export type VerificationStatus = "not_run" | "passed" | "failed" | "not_applicable" | "blocked";
export type ReviewVerdict = "pending" | "go" | "conditional" | "no-go";

export interface VerificationResult {
  status: VerificationStatus;
  summary: string;
  checks: string[];
  limitations: string[];
  notApplicableReason?: string;
}

export interface ReviewFinding {
  severity: "critical" | "major" | "minor";
  requirement: string;
  location: string;
  problem: string;
  requiredChange: string;
}

export interface ReviewState {
  verdict: ReviewVerdict;
  findings: ReviewFinding[];
  /** Number of automatic repair rounds already granted. */
  repairRounds: number;
}

export interface Task {
  id: string;
  title: string;
  goal: string;
  doneWhen: string[];
  readonly policy: Mode;
  status: TaskStatus;
  phase: TaskPhase;
  decisions: string[];
  verification: VerificationResult;
  review?: ReviewState;
  blocker?: string;
  cancelReason?: string;
  nextAction?: string;
}

export type TaskEvent =
  | { type: "begin_implementation" }
  | { type: "begin_verification" }
  | { type: "verification_passed"; status?: "passed" | "not_applicable"; summary: string; checks?: string[]; limitations?: string[]; notApplicableReason?: string }
  | { type: "verification_failed"; summary: string; checks?: string[]; limitations?: string[] }
  | { type: "review_go" }
  | { type: "review_changes_required"; verdict: "conditional" | "no-go"; findings: ReviewFinding[]; requiresUserDecision?: boolean }
  | { type: "block"; reason: string }
  | { type: "resume"; phase?: TaskPhase; decision?: string; nextAction?: string }
  | { type: "cancel"; reason: string };

const MAX_AUTOMATIC_REPAIR_ROUNDS = 2;
const TASK_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

export function createTask(input: Pick<Task, "id" | "title" | "goal" | "doneWhen" | "policy">): Task {
  if (!TASK_ID_PATTERN.test(input.id) || !input.title.trim() || !input.goal.trim()) {
    throw new Error("Task id must use 1-128 letters, digits, hyphens or underscores; title and goal are required");
  }
  if (input.doneWhen.length === 0 && input.policy === "strict") {
    throw new Error("Strict Tasks require at least one doneWhen acceptance criterion");
  }
  return {
    ...input,
    status: "active",
    phase: "prepare",
    decisions: [],
    verification: { status: "not_run", summary: "", checks: [], limitations: [] },
  };
}

function assertMutable(task: Task): void {
  if (task.status === "completed" || task.status === "cancelled") {
    throw new Error(`Task is terminal: ${task.status}`);
  }
}

function assertVerificationSufficient(task: Task): void {
  const status = task.verification.status;
  if (status !== "passed" && status !== "not_applicable") {
    throw new Error("Task cannot complete without a passed or justified not_applicable verification result");
  }
  if (status === "not_applicable" && !task.verification.notApplicableReason?.trim()) {
    throw new Error("not_applicable verification requires a reason");
  }
}

export function transitionTask(task: Task, event: TaskEvent): Task {
  if (event.type === "cancel") {
    assertMutable(task);
    if (!event.reason.trim()) throw new Error("Cancellation reason is required");
    return { ...task, status: "cancelled", cancelReason: event.reason, nextAction: undefined };
  }

  if (event.type === "block") {
    assertMutable(task);
    if (!event.reason.trim()) throw new Error("Blocker reason is required");
    return { ...task, status: "blocked", blocker: event.reason, nextAction: "Resolve the blocker, then resume at the current phase." };
  }

  if (event.type === "resume") {
    if (task.status !== "blocked") throw new Error("Only a blocked Task can be resumed");
    if (event.phase === "complete") throw new Error("A blocked Task cannot resume directly to complete");
    if (event.phase && event.phase !== task.phase && !event.decision?.trim()) {
      throw new Error("Changing phase while resuming a blocked Task requires a recorded decision");
    }
    const nextPhase = event.phase ?? task.phase;
    const phaseChangedFromReviewToImplement = task.phase === "review" && nextPhase === "implement";
    return {
      ...task,
      status: "active",
      phase: nextPhase,
      decisions: event.decision?.trim() ? [...task.decisions, event.decision.trim()] : task.decisions,
      verification: phaseChangedFromReviewToImplement
        ? { status: "not_run", summary: "", checks: [], limitations: [] }
        : task.verification,
      blocker: undefined,
      nextAction: event.nextAction,
    };
  }

  assertMutable(task);
  if (task.status === "blocked") throw new Error("A blocked Task must be resumed before phase transitions");

  switch (event.type) {
    case "begin_implementation": {
      if (task.phase !== "prepare") throw new Error("Implementation can only begin from prepare");
      return { ...task, phase: "implement", status: "active", nextAction: undefined };
    }
    case "begin_verification": {
      if (task.phase !== "implement") throw new Error("Verification can only begin after implementation");
      return {
        ...task,
        phase: "verify",
        verification: { status: "not_run", summary: "", checks: [], limitations: [] },
      };
    }
    case "verification_failed": {
      if (task.phase !== "verify") throw new Error("Verification result requires phase=verify");
      return {
        ...task,
        phase: "implement",
        status: "active",
        verification: {
          status: "failed",
          summary: event.summary,
          checks: event.checks ?? [],
          limitations: event.limitations ?? [],
        },
        nextAction: "Fix the verification failure, then verify again.",
      };
    }
    case "verification_passed": {
      if (task.phase !== "verify") throw new Error("Verification result requires phase=verify");
      const notApplicable = event.status === "not_applicable";
      if (notApplicable && !event.notApplicableReason?.trim()) {
        throw new Error("not_applicable verification requires a reason");
      }
      const verification: VerificationResult = {
        status: notApplicable ? "not_applicable" : "passed",
        summary: event.summary,
        checks: event.checks ?? [],
        limitations: event.limitations ?? [],
        ...(notApplicable ? { notApplicableReason: event.notApplicableReason } : {}),
      };
      if (task.policy === "strict") {
        return {
          ...task,
          phase: "review",
          status: "active",
          verification,
          review: task.review
            ? { ...task.review, verdict: "pending", findings: [] }
            : { verdict: "pending", findings: [], repairRounds: 0 },
          nextAction: "Run the independent reviewer against the agreed acceptance criteria and current verification result.",
        };
      }
      return { ...task, phase: "complete", status: "completed", verification, nextAction: undefined };
    }
    case "review_go": {
      if (task.policy !== "strict" || task.phase !== "review" || !task.review) {
        throw new Error("Reviewer go is only valid for a strict Task in review phase");
      }
      assertVerificationSufficient(task);
      return {
        ...task,
        phase: "complete",
        status: "completed",
        review: { ...task.review, verdict: "go", findings: [] },
        nextAction: undefined,
      };
    }
    case "review_changes_required": {
      if (task.policy !== "strict" || task.phase !== "review" || !task.review) {
        throw new Error("Review findings are only valid for a strict Task in review phase");
      }
      if (event.findings.length === 0) {
        throw new Error("A non-go review verdict requires at least one objective finding");
      }
      const review = { ...task.review, verdict: event.verdict, findings: event.findings };
      if (event.requiresUserDecision) {
        return {
          ...task,
          status: "blocked",
          review,
          blocker: "Reviewer findings require a product, business, or user decision.",
          nextAction: "Present the specific decision and recommended option to the user.",
        };
      }
      if (review.repairRounds >= MAX_AUTOMATIC_REPAIR_ROUNDS) {
        return {
          ...task,
          status: "blocked",
          review,
          blocker: `Reviewer still reports required changes after ${MAX_AUTOMATIC_REPAIR_ROUNDS} automatic repair rounds.`,
          nextAction: "Report unresolved findings and wait for a new explicit user request; do not retry automatically.",
        };
      }
      review.repairRounds += 1;
      return {
        ...task,
        phase: "implement",
        status: "active",
        review,
        verification: { status: "not_run", summary: "", checks: [], limitations: [] },
        nextAction: "Fix only the objective review findings, re-run relevant verification, then request review again.",
      };
    }
  }
}
