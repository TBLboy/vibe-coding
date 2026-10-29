import type { Task } from "./task-machine.ts";

export interface ActiveTaskPointer {
  taskID: string;
  policy: "fast" | "balanced" | "strict";
  active: boolean;
}

export interface ReviewPermit {
  taskID: string;
  consumed: boolean;
}

export function activeTaskStorageKey(sessionID: string): string {
  if (!sessionID.trim()) throw new Error("sessionID must not be empty");
  return `vibe-v2:active-task:${sessionID}`;
}

export function reviewPermitStorageKey(sessionID: string): string {
  if (!sessionID.trim()) throw new Error("sessionID must not be empty");
  return `vibe-v2:review-permit:${sessionID}`;
}

/** Set only when a reviewer permit is actually consumed by a vibe-reviewer invocation. */
export interface ReviewCompletion {
  taskID: string;
}

export function reviewCompletionStorageKey(sessionID: string): string {
  if (!sessionID.trim()) throw new Error("sessionID must not be empty");
  return `vibe-v2:review-completed:${sessionID}`;
}

export function isReviewCompletion(value: unknown, expectedTaskID: string): value is ReviewCompletion {
  if (!value || typeof value !== "object") return false;
  const completion = value as Partial<ReviewCompletion>;
  return typeof completion.taskID === "string" && completion.taskID === expectedTaskID;
}

export function isTaskPointer(value: unknown, expectedTaskID?: string): value is ActiveTaskPointer {
  if (!value || typeof value !== "object") return false;
  const pointer = value as Partial<ActiveTaskPointer>;
  return typeof pointer.taskID === "string" && pointer.taskID.length > 0 &&
    (pointer.policy === "fast" || pointer.policy === "balanced" || pointer.policy === "strict") &&
    typeof pointer.active === "boolean" && (expectedTaskID === undefined || pointer.taskID === expectedTaskID);
}

export function isActiveTaskPointer(value: unknown, expectedTaskID?: string): value is ActiveTaskPointer {
  return isTaskPointer(value, expectedTaskID) && value.active === true;
}

export function isReviewPermit(value: unknown, expectedTaskID?: string): value is ReviewPermit {
  if (!value || typeof value !== "object") return false;
  const permit = value as Partial<ReviewPermit>;
  return typeof permit.taskID === "string" && permit.taskID.length > 0 && permit.consumed === false &&
    (expectedTaskID === undefined || permit.taskID === expectedTaskID);
}

/** Validate the persisted Task snapshot before issuing a one-time reviewer permit. */
export function canAuthorizeReview(value: unknown, expectedTaskID: string): boolean {
  if (!value || typeof value !== "object" || !expectedTaskID.trim()) return false;
  const task = value as Partial<Task>;
  return (
    task.id === expectedTaskID &&
    task.policy === "strict" &&
    task.status === "active" &&
    task.phase === "review" &&
    (task.verification?.status === "passed" || task.verification?.status === "not_applicable") &&
    (task.verification?.status !== "not_applicable" || Boolean(task.verification.notApplicableReason?.trim())) &&
    task.review?.verdict === "pending" &&
    Array.isArray(task.review.findings) && task.review.findings.length === 0 &&
    Number.isInteger(task.review.repairRounds) && task.review.repairRounds >= 0 && task.review.repairRounds <= 2 &&
    Array.isArray(task.doneWhen) && task.doneWhen.length > 0
  );
}

/**
 * @param reviewerInvoked whether the plugin observed a consumed reviewer permit for this Task.
 * A strict Task whose review verdict was written without the reviewer ever being invoked cannot close.
 */
export function canCloseTask(value: unknown, expectedTaskID: string, reviewerInvoked = true): boolean {
  if (!value || typeof value !== "object" || !expectedTaskID.trim()) return false;
  const task = value as Partial<Task>;
  if (task.id !== expectedTaskID) return false;
  if (task.policy !== "fast" && task.policy !== "balanced" && task.policy !== "strict") return false;
  if (task.status === "cancelled") return Boolean(task.cancelReason?.trim());
  if (task.status !== "completed" || task.phase !== "complete") return false;
  if (task.verification?.status !== "passed" && task.verification?.status !== "not_applicable") return false;
  if (task.verification.status === "not_applicable" && !task.verification.notApplicableReason?.trim()) return false;
  if (task.policy === "strict" && (task.review?.verdict !== "go" || task.review.findings.length !== 0)) return false;
  if (task.policy === "strict" && !reviewerInvoked) return false;
  return true;
}
