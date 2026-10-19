import type { Mode } from "./mode.ts";

export interface TaskNeedSignals {
  /** Work will span sessions or cannot be completed in the current execution window. */
  crossSession?: boolean;
  /** A future agent must be able to restore the exact unfinished work. */
  needsRecovery?: boolean;
  /** Work is currently blocked and needs durable follow-up. */
  blocked?: boolean;
  /** The request has multiple independently trackable deliverables. */
  multipleDeliverables?: boolean;
  /** The user supplied meaningful acceptance criteria that must persist. */
  explicitAcceptanceCriteria?: boolean;
  /** A durable business or technical decision was made. */
  durableDecision?: boolean;
  /** A material risk makes explicit task state useful even if the patch is small. */
  highRisk?: boolean;
  /** More than one meaningful implementation step is expected. */
  multiStep?: boolean;
  /** The change spans multiple files or modules. */
  multiFile?: boolean;
  /** The work has a durable deliverable boundary. */
  durableDeliverable?: boolean;
}

const ALWAYS_PERSIST = [
  "crossSession",
  "needsRecovery",
  "blocked",
  "multipleDeliverables",
  "explicitAcceptanceCriteria",
  "durableDecision",
  "highRisk",
  "durableDeliverable",
] as const satisfies readonly (keyof TaskNeedSignals)[];

export function shouldCreateTask(mode: Mode, signals: TaskNeedSignals): boolean {
  if (mode === "strict") return true;
  if (ALWAYS_PERSIST.some((key) => signals[key] === true)) return true;
  if (mode === "fast") return false;
  return signals.multiStep === true || signals.multiFile === true;
}
