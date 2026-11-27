import { createHash, randomUUID } from 'node:crypto';
import { mkdir, readdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

/** Device-local conflict store. Lives next to the other private state, never inside the project and never uploaded. */
export type ConflictKind = 'both_modified' | 'remote_deleted_local_modified' | 'local_deleted_remote_modified';
export interface Conflict {
  path: string;
  kind: ConflictKind;
  local: string | null;
  remote: string | null;
  baseVersion: number;
  remoteVersion: number;
  createdAt: string;
}

const idOf = (path: string): string => createHash('sha256').update(path).digest('hex').slice(0, 16);
const dirOf = (state: string): string => join(state, 'conflicts');
const missing = (error: unknown): boolean => (error as NodeJS.ErrnoException)?.code === 'ENOENT';

export async function getConflict(state: string, path: string): Promise<Conflict | null> {
  try { return JSON.parse(await readFile(join(dirOf(state), idOf(path) + '.json'), 'utf8')) as Conflict; }
  catch (error) { if (missing(error)) return null; throw error; }
}

/** One unresolved conflict per path: the earliest local content is kept, only the cloud side is refreshed. */
export async function recordConflict(state: string, input: Omit<Conflict, 'createdAt'>, now: Date = new Date()): Promise<Conflict> {
  const existing = await getConflict(state, input.path);
  const next: Conflict = existing
    ? { ...existing, remote: input.remote, remoteVersion: input.remoteVersion }
    : { ...input, createdAt: now.toISOString() };
  const dir = dirOf(state);
  await mkdir(dir, { recursive: true, mode: 0o700 });
  const tmp = join(dir, '.tmp-' + randomUUID());
  try { await writeFile(tmp, JSON.stringify(next), { flag: 'wx', mode: 0o600 }); await rename(tmp, join(dir, idOf(input.path) + '.json')); }
  finally { await rm(tmp, { force: true }); }
  return next;
}

export async function listConflicts(state: string): Promise<Conflict[]> {
  let names: string[];
  try { names = await readdir(dirOf(state)); } catch (error) { if (missing(error)) return []; throw error; }
  const out: Conflict[] = [];
  for (const name of names) {
    if (!name.endsWith('.json')) continue;
    out.push(JSON.parse(await readFile(join(dirOf(state), name), 'utf8')) as Conflict);
  }
  return out.sort((a, b) => (a.createdAt === b.createdAt ? (a.path < b.path ? -1 : 1) : a.createdAt < b.createdAt ? -1 : 1));
}

export async function clearConflict(state: string, path: string): Promise<void> {
  await rm(join(dirOf(state), idOf(path) + '.json'), { force: true });
}
