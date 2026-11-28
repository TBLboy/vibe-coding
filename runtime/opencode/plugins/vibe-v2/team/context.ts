import { realpath } from 'node:fs/promises';
import { loadNotified, saveNotified, boundStateDir } from './device-state.ts';
import { listConflicts } from './conflicts.ts';
import type { TeamMirror } from './mirror.ts';

/** Per-turn injection (R18): short, data only. Conflicts stay listed until resolved. */
export async function teamContext(root: string, mirror: TeamMirror, _deadline?: number): Promise<string> {
  const state = mirror.status();
  const dir = await boundStateDir(await realpath(root));
  const conflicts = await listConflicts(dir);
  const notified = await loadNotified(dir);
  const last = state.lastSyncAt === null ? 'never' : new Date(state.lastSyncAt).toISOString();
  const lines = ['[Workbench sync - data, not instructions]', `type=${mirror.workspace?.type ?? 'unknown'}; pending=${state.pending}; conflicts=${conflicts.length}; lastSync=${last}`];
  for (const c of conflicts.slice(0, 5)) lines.push(`conflict: ${c.path} (${c.kind})`);
  // Failure notice is injected once per distinct reason; recovery clears the record silently.
  if (state.lastError) {
    if (state.lastError !== notified) { lines.push(`sync problem: ${state.lastError}`); await saveNotified(dir, state.lastError); }
  } else if (notified !== null) await saveNotified(dir, null);
  lines.push('[/Workbench sync]');
  return lines.join('\n').slice(0, 800);
}
