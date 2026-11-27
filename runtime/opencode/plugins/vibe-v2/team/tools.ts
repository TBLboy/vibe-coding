import { realpath } from 'node:fs/promises';
import type { ToolDefinition } from '../host-contract.ts';
import { loadBinding, connectWorkspace } from './binding.ts';
import { clearDeviceBinding, stateDir } from './device-state.ts';
import { listConflicts } from './conflicts.ts';
import { TeamError } from './client.ts';
import type { TeamMirror } from './mirror.ts';

export const RESOLUTIONS = ['keep_remote', 'keep_local', 'merged', 'accept_delete', 'keep_modified'] as const;

interface Spec { name: string; description: string; properties: Record<string, unknown>; required?: string[]; run: (input: Record<string, unknown>, signal?: AbortSignal) => Promise<unknown> }

export function workspaceTools(root: string, mirror: TeamMirror, allowed: (sessionID: string) => Promise<boolean>): ToolDefinition[] {
  const specs: Spec[] = [
    { name: 'workspace_connect', description: 'Bind this project root to a Workbench workspace with its Key, then sync once. Never rebinds silently.', properties: { key: { type: 'string' }, serverUrl: { type: 'string' } }, required: ['key'], run: async (i, s) => {
      const binding = await loadBinding(root), serverUrl = typeof i.serverUrl === 'string' ? i.serverUrl : binding?.serverUrl ?? process.env.WORKBENCH_URL;
      if (typeof i.key !== 'string' || !serverUrl) throw new TeamError('connect_requires_key_and_server_url');
      const result = await connectWorkspace(root, { serverUrl, key: i.key }, s);
      if (result.status === 'bound_to_other') return result;
      return { ...result, sync: await mirror.sync(true, s) };
    } },
    { name: 'workspace_status', description: 'Read-only: last sync time, pending changes, unresolved conflicts and warnings.', properties: {}, run: async () => {
      const binding = await loadBinding(root);
      if (!binding) return { bound: false };
      const state = await mirror.inspect();
      const conflicts = (await listConflicts(stateDir(await realpath(root)))).map((c) => ({ path: c.path, kind: c.kind }));
      return { bound: true, workspaceId: binding.workspaceId, workspaceType: binding.workspaceType, ...state, conflictList: conflicts };
    } },
    { name: 'workspace_sync', description: 'Force an immediate two-way sync (fallback; sync normally runs automatically).', properties: {}, run: (_, s) => mirror.sync(true, s) },
    { name: 'workspace_disconnect', description: 'Remove this machine binding and Key. Local files, manifest and conflicts are kept.', properties: {}, run: async () => {
      await clearDeviceBinding(stateDir(await realpath(root)));
      return { status: 'disconnected' };
    } },
    { name: 'workspace_resolve_conflict', description: 'Apply the user decision for one conflict. Never choose a side without the user.', properties: { path: { type: 'string' }, resolution: { type: 'string', enum: [...RESOLUTIONS] }, content: { type: 'string' } }, required: ['path', 'resolution'], run: (i, s) => {
      if (typeof i.path !== 'string' || !RESOLUTIONS.includes(i.resolution as never)) throw new TeamError('invalid_resolution');
      return mirror.resolveConflict(i.path, i.resolution as (typeof RESOLUTIONS)[number], typeof i.content === 'string' ? i.content : undefined, s);
    } },
  ];
  return specs.map((spec) => ({
    name: spec.name,
    description: spec.description,
    input: { type: 'object', properties: spec.properties, required: spec.required ?? [], additionalProperties: false },
    execute: async (input, context) => {
      if (context.agent !== 'vibe-main' || !await allowed(context.sessionID)) return { content: 'Rejected: workspace Session mismatch or reviewer.' };
      if (spec.name !== 'workspace_connect' && !await loadBinding(root)) return { content: JSON.stringify({ error: 'not_bound' }) };
      try { return { content: JSON.stringify(await spec.run(input, context.signal)) }; }
      catch (error) { return { content: JSON.stringify({ error: error instanceof TeamError ? error.code : 'local_workspace_failed' }) }; }
    },
  }));
}
