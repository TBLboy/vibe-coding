export interface ActiveTaskPointer {
  taskID: string;
  policy: "fast" | "balanced" | "strict";
  active: boolean;
}

export function activeTaskStorageKey(sessionID: string): string {
  if (!sessionID.trim()) throw new Error("sessionID must not be empty");
  return `vibe-v2:active-task:${sessionID}`;
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
