import { realpath } from 'node:fs/promises';
import { TeamClient, TeamError, object } from './client.ts';
import { loadDeviceBinding, loadKey, saveDeviceBinding, saveKey, stateDir, validateDeviceBinding, type DeviceBinding } from './device-state.ts';

export interface Credentials extends DeviceBinding { key: string }

async function dirOf(root: string): Promise<string> { return stateDir(await realpath(root)); }

export async function loadBinding(root: string): Promise<DeviceBinding | null> {
  return loadDeviceBinding(await dirOf(root));
}

export async function loadCredentials(root: string): Promise<Credentials> {
  const dir = await dirOf(root), binding = await loadDeviceBinding(dir), key = await loadKey(dir);
  if (!binding || !key) throw new TeamError('credentials_missing');
  return { ...binding, key };
}

export type ConnectResult =
  | { status: 'connected' | 'already_connected'; workspaceId: string; workspaceName: string; workspaceType: string }
  | { status: 'bound_to_other'; workspaceId: string; workspaceType: string };

/** Bind a project root to a workspace by Key. Never rebinds silently; the Key is stored only in the device-private directory. */
export async function connectWorkspace(root: string, input: { serverUrl: string; key: string }, signal?: AbortSignal): Promise<ConnectResult> {
  const dir = await dirOf(root);
  const url = validateDeviceBinding({ workspaceId: 'pending', workspaceType: 'pending', serverUrl: input.serverUrl }).serverUrl;
  if (!/^[A-Za-z0-9_-]{32}$/u.test(input.key)) throw new TeamError('invalid_credentials');
  const result = await new TeamClient(url, input.key).request('/connect', 'POST', {}, {}, Date.now() + 5000, signal);
  const ws = object(result.workspace);
  const next = validateDeviceBinding({ workspaceId: ws.id, workspaceType: ws.type, serverUrl: url });
  const existing = await loadDeviceBinding(dir);
  if (existing && existing.workspaceId !== next.workspaceId) return { status: 'bound_to_other', workspaceId: existing.workspaceId, workspaceType: existing.workspaceType };
  await saveKey(dir, input.key);
  await saveDeviceBinding(dir, next);
  return { status: existing ? 'already_connected' : 'connected', workspaceId: next.workspaceId, workspaceName: String(ws.name ?? ''), workspaceType: next.workspaceType };
}
