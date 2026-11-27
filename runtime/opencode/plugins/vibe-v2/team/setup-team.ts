import { realpath } from 'node:fs/promises';
import type { HostContext } from '../host-contract.ts';
import { TeamMirror } from './mirror.ts';
import { workspaceTools } from './tools.ts';
import { teamContext } from './context.ts';
import { shouldEnableTeamModules } from './gate.ts';
import { resolveSyncInterval, startPeriodicSync } from './periodic-sync.ts';

const WRITE_TOOLS = new Set(['write', 'edit', 'shell']);
const END_OF_TURN_DEBOUNCE_MS = 2000;

/** Always wired; binding is checked on every use so an unbound root exposes only workspace_connect and sends no request. */
export async function setupTeam(ctx: HostContext, root: string, memoryRootFor: (sessionID: string) => Promise<string | null>): Promise<() => void> {
  root = await realpath(root);
  const mirror = new TeamMirror(root);
  const allowed = async (sessionID: string): Promise<boolean> => {
    try {
      const info = await ctx.session.get({ sessionID }) as { parentID?: string; agent?: string };
      return !info.parentID && info.agent !== 'vibe-reviewer' && await memoryRootFor(sessionID) === root;
    } catch { return false; }
  };
  const syncIfBound = async (): Promise<void> => { if (await shouldEnableTeamModules(root)) await mirror.sync(); };

  await ctx.tool.transform((editor) => { for (const tool of workspaceTools(root, mirror, allowed)) editor.add(tool); });

  await ctx.session.hook('context', async (event) => {
    if (!await allowed(event.sessionID) || !await shouldEnableTeamModules(root)) return;
    await mirror.sync(false, undefined, 1500);
    try { event.system.push({ type: 'text', text: await teamContext(root, mirror) }); }
    catch { event.system.push({ type: 'text', text: 'Workbench sync state unavailable; no automatic reset or deletion performed.' }); }
  });

  // The host has no end-of-turn hook: a completed write-type tool schedules one debounced sync (best effort, the timer retries anyway).
  let pendingTimer: ReturnType<typeof setTimeout> | undefined;
  await ctx.tool.hook('execute.after', async (event) => {
    if (event.status !== 'completed' || event.agent !== 'vibe-main' || !WRITE_TOOLS.has(event.tool)) return;
    if (pendingTimer) clearTimeout(pendingTimer);
    pendingTimer = setTimeout(() => { void syncIfBound().catch(() => {}); }, END_OF_TURN_DEBOUNCE_MS);
    pendingTimer.unref?.();
  });

  const stopPeriodic = startPeriodicSync({ intervalMs: resolveSyncInterval(process.env.VIBE_TEAM_SYNC_INTERVAL_MS), sync: syncIfBound });
  return () => { if (pendingTimer) clearTimeout(pendingTimer); stopPeriodic(); };
}
