import { createHash, randomUUID } from 'node:crypto';
import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { assertId } from '../../../../../shared/team-contracts/binding.ts';

/** Device-private sync state lives outside the project's .vibe/ and is never uploaded. */
export interface DeviceBinding { workspaceId: string; workspaceType: string; serverUrl: string }

const TYPE = /^[a-z][a-z0-9-]{0,63}$/u;
const KEY = /^[A-Za-z0-9_-]{32}$/u;

export function stateDir(realRoot: string, env: NodeJS.ProcessEnv = process.env): string {
  const base = env.OPENCODE_CONFIG_DIR || join(homedir(), '.config', 'opencode');
  return join(base, 'vibe-worklog', createHash('sha256').update(realRoot).digest('hex').slice(0, 16));
}

export function validateDeviceBinding(value: unknown): DeviceBinding {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error('invalid binding');
  const c = value as Record<string, unknown>;
  assertId(c.workspaceId, 'workspaceId');
  if (typeof c.workspaceType !== 'string' || !TYPE.test(c.workspaceType)) throw new Error('invalid workspaceType');
  let url: URL;
  try { url = new URL(String(c.serverUrl)); } catch { throw new Error('invalid serverUrl'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.search || url.hash || url.username || url.password) throw new Error('invalid serverUrl');
  return { workspaceId: c.workspaceId, workspaceType: c.workspaceType, serverUrl: url.origin + (url.pathname === '/' ? '' : url.pathname) };
}

async function writePrivate(dir: string, name: string, text: string): Promise<void> {
  await mkdir(dir, { recursive: true, mode: 0o700 });
  const tmp = join(dir, '.tmp-' + randomUUID());
  try { await writeFile(tmp, text, { flag: 'wx', mode: 0o600 }); await rename(tmp, join(dir, name)); }
  finally { await rm(tmp, { force: true }); }
}
async function readJson(dir: string, name: string): Promise<unknown | null> {
  try { return JSON.parse(await readFile(join(dir, name), 'utf8')); }
  catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null; throw error; }
}

export async function loadDeviceBinding(dir: string): Promise<DeviceBinding | null> {
  const raw = await readJson(dir, 'binding.json');
  return raw === null ? null : validateDeviceBinding(raw);
}
export async function saveDeviceBinding(dir: string, binding: DeviceBinding): Promise<void> {
  await writePrivate(dir, 'binding.json', JSON.stringify(validateDeviceBinding(binding)));
}
export async function loadKey(dir: string): Promise<string | null> {
  const raw = await readJson(dir, 'credentials.json') as { key?: unknown } | null;
  if (raw === null) return null;
  if (typeof raw.key !== 'string' || !KEY.test(raw.key)) throw new Error('credentials_invalid');
  return raw.key;
}
export async function saveKey(dir: string, key: string): Promise<void> {
  if (!KEY.test(key)) throw new Error('invalid key');
  await writePrivate(dir, 'credentials.json', JSON.stringify({ key }));
}
/** Last sync failure reason already shown to the user (R25: notify once, again only when the reason changes). */
export async function loadNotified(dir: string): Promise<string | null> {
  const raw = await readJson(dir, 'status.json') as { notified?: unknown } | null;
  return raw && typeof raw.notified === 'string' ? raw.notified : null;
}
export async function saveNotified(dir: string, reason: string | null): Promise<void> {
  await writePrivate(dir, 'status.json', JSON.stringify({ notified: reason }));
}
/** Disconnect: drop binding and credentials, keep manifest and conflict store. */
export async function clearDeviceBinding(dir: string): Promise<void> {
  await rm(join(dir, 'binding.json'), { force: true });
  await rm(join(dir, 'credentials.json'), { force: true });
}
