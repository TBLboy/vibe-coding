import type { ConflictKind } from './conflicts.ts';

export interface Entry { version: number; hash: string }
export type PushAction = { action: 'noop' } | { action: 'push'; baseVersion: number } | { action: 'pushDelete'; baseVersion: number };
export type PullAction = { action: 'adopt' } | { action: 'apply' } | { action: 'conflict'; kind: ConflictKind };

/** Local change vs. the last synced baseline. No accounts, owners or layers: every synced path is writable. */
export function planPush(entry: Entry | undefined, localHash: string | null): PushAction {
  if (!entry) return localHash === null ? { action: 'noop' } : { action: 'push', baseVersion: 0 };
  if (localHash === null) return { action: 'pushDelete', baseVersion: entry.version };
  return localHash === entry.hash ? { action: 'noop' } : { action: 'push', baseVersion: entry.version };
}

/**
 * Cloud change arriving for a path (remoteHash null = deletion; also used after a 409).
 * adopt: local already equals cloud, only the baseline moves. apply: local is untouched since the baseline, take cloud.
 * conflict: local has unsynced changes that differ from cloud; cloud lands on the original path, local goes to the conflict store.
 */
export function planPull(entry: Entry | undefined, localHash: string | null, remoteHash: string | null): PullAction {
  if (localHash === remoteHash) return { action: 'adopt' };
  const untouched = entry ? localHash === entry.hash : localHash === null;
  if (untouched) return { action: 'apply' };
  const kind: ConflictKind = localHash === null ? 'local_deleted_remote_modified' : remoteHash === null ? 'remote_deleted_local_modified' : 'both_modified';
  return { action: 'conflict', kind };
}
