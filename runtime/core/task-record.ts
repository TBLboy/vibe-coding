import { MODES } from "./mode.ts";

const TASK_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;
const STATUSES = ["active", "blocked", "completed", "cancelled"] as const;
const PHASES = ["prepare", "implement", "verify", "review", "complete"] as const;
const VERIFICATION_STATUSES = ["not_run", "passed", "failed", "not_applicable", "blocked"] as const;
const REVIEW_VERDICTS = ["pending", "go", "conditional", "no-go"] as const;
const FINDING_SEVERITIES = ["critical", "major", "minor"] as const;

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function oneOf(list: readonly string[], value: unknown): boolean {
  return typeof value === "string" && list.includes(value);
}

/**
 * Structural validation of a persisted Task record against `schemas/task.schema.json`
 * and the invariants of `task-machine.ts`. Returns a list of human-readable problems;
 * an empty list means the record is acceptable. Kept dependency-free on purpose.
 */
export function validateTaskRecord(value: unknown, expectedTaskID?: string): string[] {
  const problems: string[] = [];
  if (!value || typeof value !== "object" || Array.isArray(value)) return ["Task record must be a JSON object"];
  const task = value as Record<string, unknown>;

  if (typeof task.id !== "string" || !TASK_ID_PATTERN.test(task.id)) problems.push("id must use 1-128 letters, digits, hyphens or underscores");
  else if (expectedTaskID !== undefined && task.id !== expectedTaskID) problems.push(`id ${task.id} does not match ${expectedTaskID}`);
  if (typeof task.title !== "string" || !task.title.trim()) problems.push("title is required");
  if (typeof task.goal !== "string" || !task.goal.trim()) problems.push("goal is required");
  if (!isStringArray(task.doneWhen)) problems.push("doneWhen must be an array of strings");
  if (!oneOf(MODES, task.policy)) problems.push("policy must be fast, balanced or strict");
  if (!oneOf(STATUSES, task.status)) problems.push("status is invalid");
  if (!oneOf(PHASES, task.phase)) problems.push("phase is invalid");
  if (!isStringArray(task.decisions)) problems.push("decisions must be an array of strings");

  const verification = task.verification;
  if (!verification || typeof verification !== "object") problems.push("verification object is required");
  else {
    const record = verification as Record<string, unknown>;
    if (!oneOf(VERIFICATION_STATUSES, record.status)) problems.push("verification.status is invalid");
    if (typeof record.summary !== "string") problems.push("verification.summary must be a string");
    if (!isStringArray(record.checks)) problems.push("verification.checks must be an array of strings");
    if (!isStringArray(record.limitations)) problems.push("verification.limitations must be an array of strings");
    if (record.status === "not_applicable" && (typeof record.notApplicableReason !== "string" || !record.notApplicableReason.trim())) {
      problems.push("not_applicable verification requires notApplicableReason");
    }
  }

  if (task.review !== undefined) {
    const review = task.review;
    if (!review || typeof review !== "object") problems.push("review must be an object when present");
    else {
      const record = review as Record<string, unknown>;
      if (!oneOf(REVIEW_VERDICTS, record.verdict)) problems.push("review.verdict is invalid");
      if (!Array.isArray(record.findings)) problems.push("review.findings must be an array");
      else {
        for (const finding of record.findings) {
          const item = finding as Record<string, unknown> | null;
          if (!item || typeof item !== "object" || !oneOf(FINDING_SEVERITIES, item.severity) ||
            ["requirement", "location", "problem", "requiredChange"].some((key) => typeof item[key] !== "string")) {
            problems.push("review.findings entries must carry severity, requirement, location, problem and requiredChange");
            break;
          }
        }
      }
      if (!Number.isInteger(record.repairRounds) || (record.repairRounds as number) < 0 || (record.repairRounds as number) > 2) {
        problems.push("review.repairRounds must be an integer from 0 to 2");
      }
    }
  }

  for (const key of ["blocker", "cancelReason", "nextAction"]) {
    if (task[key] !== undefined && typeof task[key] !== "string") problems.push(`${key} must be a string when present`);
  }

  // Cross-field invariants from the Task state machine.
  if (task.policy === "strict" && isStringArray(task.doneWhen) && task.doneWhen.length === 0) problems.push("strict Tasks require at least one doneWhen criterion");
  if (task.status === "blocked" && (typeof task.blocker !== "string" || !task.blocker.trim())) problems.push("blocked Tasks require a blocker");
  if (task.status === "cancelled" && (typeof task.cancelReason !== "string" || !task.cancelReason.trim())) problems.push("cancelled Tasks require a cancelReason");
  if (task.status === "completed" && task.phase !== "complete") problems.push("completed Tasks must be in phase complete");
  if (task.phase === "review" && task.policy !== "strict") problems.push("only strict Tasks enter the review phase");
  if (task.phase === "review" && task.review === undefined) problems.push("review phase requires a review object");

  return problems;
}
