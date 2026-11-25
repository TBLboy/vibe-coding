import { assertId } from "../../../shared/team-contracts/binding.ts";
import { layerOf } from "../../../shared/team-contracts/layout.ts";
import { classifyLocal, type ManifestEntry } from "../../../shared/team-contracts/manifest.ts";
import { projectServerPath } from "./projection.ts";

export type WriteWarningCode = "namespace" | "not-owner" | "server-managed" | "unmapped" | "conflict";
export interface WriteWarning { code: WriteWarningCode; message: string }
export interface WriteDecision {
  action: "noop" | "push" | "pushDelete" | "restore" | "ignore" | "markSynced" | "conflictCopy";
  reason: string;
  warnings: WriteWarning[];
  baseVersion?: number;
  preserveLocal?: boolean;
  version?: number;
  hash?: string | null;
}

export interface LocalWriteInput {
  serverPath: string;
  entry?: ManifestEntry;
  localHash: string | null;
  accountId: string;
  ownerAccountId: string | null;
}

const HASH = /^[0-9a-f]{64}$/u;
function assertHash(value: unknown): asserts value is string | null {
  if (value !== null && (typeof value !== "string" || !HASH.test(value))) throw new Error("invalid content hash");
}

function restore(code: Exclude<WriteWarningCode, "unmapped" | "conflict">, message: string, localHash: string | null): WriteDecision {
  return { action: "restore", reason: code, warnings: [{ code, message }], preserveLocal: localHash !== null };
}

/** Pure policy only. Callers must authenticate first; no decision authorizes an
 * I/O executor to remove untracked files or discard unsaved local bytes. */
export function routeLocalWrite(input: LocalWriteInput): WriteDecision {
  const projection = projectServerPath(input.serverPath);
  const layer = layerOf(input.serverPath);
  assertId(input.accountId, "accountId");
  if (input.ownerAccountId !== null) assertId(input.ownerAccountId, "accountId");
  assertHash(input.localHash);
  if (input.entry !== undefined) {
    if (input.entry === null || typeof input.entry !== "object" || !Number.isSafeInteger(input.entry.version) || input.entry.version < 1) {
      throw new Error("invalid manifest entry version");
    }
    assertHash(input.entry.hash);
    if (input.entry.hash === null) throw new Error("invalid manifest entry hash");
  }
  const state = classifyLocal(input.entry, input.localHash);
  if (state === "unchanged") return { action: "noop", reason: "unchanged", warnings: [] };
  if (projection.kind === "unmapped") {
    return { action: "ignore", reason: "unmapped", warnings: [{ code: "unmapped", message: "映射区外文件已忽略，不会自动删除。" }] };
  }
  if (layer === "members" && !input.serverPath.startsWith(`members/${input.accountId}/`)) {
    return restore("namespace", "只能写入自己的 members 命名空间。", input.localHash);
  }
  if ((layer === "constitution" || layer === "specs") && input.accountId !== input.ownerAccountId) {
    return restore("not-owner", `该文档由 ${input.ownerAccountId ?? "负责人"} 维护，请联系负责人。`, input.localHash);
  }
  if (layer === "work" || layer === "activity" || layer === "index") {
    return restore("server-managed", "该记录由服务端或专用工具维护，不能直接写入。", input.localHash);
  }
  return {
    action: state === "missing" ? "pushDelete" : "push",
    reason: layer === "members" ? "own-namespace" : "owner",
    warnings: [],
    baseVersion: input.entry?.version ?? 0,
  };
}

/** Resolve a 409 from authoritative metadata, never retry it blindly. A null
 * current hash is an absent document or versioned deletion tombstone. */
export function routeWriteConflict(input: {
  localHash: string | null;
  currentHash: string | null;
  currentVersion: number;
}): WriteDecision {
  assertHash(input.localHash); assertHash(input.currentHash);
  if (!Number.isSafeInteger(input.currentVersion) || input.currentVersion < 0 || (input.currentVersion === 0 && input.currentHash !== null)) {
    throw new Error("invalid current version");
  }
  if (input.localHash === input.currentHash) {
    return { action: "markSynced", reason: "same-content", warnings: [], version: input.currentVersion, hash: input.currentHash };
  }
  return {
    action: "conflictCopy", reason: "version-conflict", preserveLocal: input.localHash !== null,
    warnings: [{ code: "conflict", message: "版本冲突；保留现有本地内容并恢复服务端版本，不自动重试写入。" }],
  };
}
