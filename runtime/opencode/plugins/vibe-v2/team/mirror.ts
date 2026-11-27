import { mkdir, readFile, realpath, rename, rm, writeFile } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { join } from 'node:path';
import { parseManifest, serializeManifest, hashContent, type Manifest } from '../../../../../shared/team-contracts/manifest.ts';
import { validateChanges } from '../../../../../shared/team-contracts/change-feed.ts';
import { validateSyncPath } from '../../../../../shared/team-contracts/layout.ts';
import { loadCredentials, type Credentials } from './binding.ts';
import { stateDir } from './device-state.ts';
import { SafeFiles } from './files.ts';
import { TeamClient, TeamError, object } from './client.ts';
import { scanSyncFiles, MAX_SYNC_BYTES } from './scan.ts';
import { planPull, planPush } from './sync-plan.ts';
import { clearConflict, getConflict, listConflicts, recordConflict } from './conflicts.ts';

const hash = (b: Buffer | null): string | null => (b === null ? null : hashContent(b));
const active = new Set<string>();

export interface SyncResult { ok: boolean; cursor: number; warnings: string[]; lastError: string | null; lastSyncAt: number | null; pending: number; conflicts: number; halted: string | null }

/** Two-way sync of AGENTS.md and .vibe/ against one workspace. Device state (manifest, conflicts, Key) lives outside the project. */
export class TeamMirror {
  readonly root: string;
  readonly files: SafeFiles;
  readonly options: { budgetMs?: number; now?: () => number };
  workspace: { type: string } | null = null;
  private manifest: Manifest = { schemaVersion: 1, cursor: 0, entries: {} };
  private creds: Credentials | null = null;
  private client: TeamClient | null = null;
  private dir = '';
  private deadline = 0;
  private signal?: AbortSignal;
  private warnings = new Set<string>();
  private lastSyncAt: number | null = null;
  private lastError: string | null = null;
  private halted: string | null = null;
  private pending = 0;
  private conflictCount = 0;
  private failures = 0;
  private nextAttempt = 0;

  constructor(root: string, options: { budgetMs?: number; now?: () => number } = {}) { this.root = root; this.options = options; this.files = new SafeFiles(root); }

  status(ok = this.lastError === null): SyncResult {
    return { ok, cursor: this.manifest.cursor, warnings: [...this.warnings].slice(-50), lastError: this.lastError, lastSyncAt: this.lastSyncAt, pending: this.pending, conflicts: this.conflictCount, halted: this.halted };
  }
  private warn(m: string): void { this.warnings.add(m); if (this.warnings.size > 100) this.warnings.delete(this.warnings.values().next().value!); }
  private check(): void { if (this.signal?.aborted || Date.now() >= this.deadline) throw new TeamError('budget_exhausted'); }
  private entry(path: string) { return Object.hasOwn(this.manifest.entries, path) ? this.manifest.entries[path] : undefined; }
  private setEntry(path: string, version: number, h: string | null): void {
    if (h === null) delete this.manifest.entries[path];
    else Object.defineProperty(this.manifest.entries, path, { value: { version, hash: h }, enumerable: true, configurable: true, writable: true });
  }
  private async loadManifest(): Promise<Manifest> {
    try { return parseManifest(await readFile(join(this.dir, 'manifest.json'), 'utf8')); }
    catch (error) { if ((error as NodeJS.ErrnoException).code === 'ENOENT') return { schemaVersion: 1, cursor: 0, entries: {} }; throw new TeamError('manifest_corrupt'); }
  }
  private async save(): Promise<void> {
    await mkdir(this.dir, { recursive: true, mode: 0o700 });
    const tmp = join(this.dir, '.tmp-' + randomUUID());
    try { await writeFile(tmp, serializeManifest(this.manifest), { flag: 'wx', mode: 0o600 }); await rename(tmp, join(this.dir, 'manifest.json')); }
    finally { await rm(tmp, { force: true }); }
  }
  private prefix(): string { return `/workspaces/${this.creds!.workspaceId}`; }
  private request(path: string, method = 'GET', body?: unknown, headers: Record<string, string> = {}) { this.check(); return this.client!.request(path, method, body, headers, this.deadline, this.signal); }
  private docUrl(path: string): string { return `${this.prefix()}/documents/${encodeURIComponent(path)}`; }

  private async current(path: string): Promise<{ version: number; hash: string | null; content: string | null } | null> {
    try {
      const d = object(await this.request(this.docUrl(path)));
      if (d.path !== path || !Number.isSafeInteger(d.version) || d.version < 1) throw new TeamError('invalid_response');
      if (d.content === null) return { version: d.version, hash: null, content: null };
      if (typeof d.content !== 'string' || hashContent(d.content) !== d.hash) throw new TeamError('invalid_content_hash');
      return { version: d.version, hash: d.hash, content: d.content };
    } catch (error) { if (error instanceof TeamError && error.status === 404) return null; throw error; }
  }

  /** Cloud state for one path arrives (content null = deleted). Local unsynced work is never overwritten; it goes to the conflict store. */
  private async applyRemote(path: string, content: string | null, version: number, h: string | null): Promise<void> {
    this.check();
    const snap = await this.files.read(path), e = this.entry(path), plan = planPull(e, hash(snap), h);
    if (plan.action === 'conflict') {
      await recordConflict(this.dir, { path, kind: plan.kind, local: snap === null ? null : snap.toString('utf8'), remote: content, baseVersion: e?.version ?? 0, remoteVersion: version });
      this.warn(`conflict: ${path}`);
    }
    if (plan.action !== 'adopt') {
      if (content === null) { if (snap !== null) await this.files.remove(path, hash(snap)!); }
      else await this.files.write(path, content, hash(snap));
    }
    this.setEntry(path, version, h);
  }

  private async pull(): Promise<void> {
    for (;;) {
      this.check();
      const v = await this.request(`${this.prefix()}/changes?since=${this.manifest.cursor}&limit=200`);
      validateChanges(this.manifest.cursor, v.changes);
      if (typeof v.hasMore !== 'boolean' || (v.hasMore && v.changes.length === 0)) throw new TeamError('invalid_batch');
      for (const c of v.changes as { seq: number; path: string; op: string; version: number; hash?: string; content?: string }[]) {
        const known = this.entry(c.path);
        if (!validateSyncPath(c.path).ok) this.warn(`skipped (invalid path): ${c.path}`);
        else if (!known || known.version < c.version) {
          if (c.op === 'delete') await this.applyRemote(c.path, null, c.version, null);
          else {
            if (typeof c.content !== 'string' || hashContent(c.content) !== c.hash) throw new TeamError('invalid_content_hash');
            await this.applyRemote(c.path, c.content, c.version, c.hash!);
          }
        }
        this.manifest.cursor = c.seq;
        await this.save();
      }
      if (!v.hasMore) return;
    }
  }

  private async push(): Promise<void> {
    const scan = await scanSyncFiles(this.root, () => this.check());
    scan.warnings.forEach((w) => this.warn(w));
    for (const path of [...new Set([...scan.files, ...Object.keys(this.manifest.entries)])].sort()) {
      this.check();
      const snap = await this.files.read(path), plan = planPush(this.entry(path), hash(snap));
      if (plan.action === 'noop') continue;
      let content: string | null = null;
      if (snap !== null) {
        if (snap.byteLength > MAX_SYNC_BYTES) continue;
        try { content = new TextDecoder('utf-8', { fatal: true }).decode(snap); } catch { continue; }
      }
      this.pending++;
      try {
        const r = await this.request(this.docUrl(path), plan.action === 'pushDelete' ? 'DELETE' : 'PUT', plan.action === 'pushDelete' ? undefined : { content }, { 'if-match': String(plan.baseVersion) });
        if (!Number.isSafeInteger(r.version) || r.version < 1 || r.hash !== hash(snap)) throw new TeamError('invalid_response');
        this.setEntry(path, r.version, hash(snap));
      } catch (error) {
        if (!(error instanceof TeamError) || error.status !== 409) throw error;
        const doc = await this.current(path);
        if (doc) await this.applyRemote(path, doc.content, doc.version, doc.hash); else this.warn(`untracked after conflict: ${path}`);
      }
      await this.save();
      this.pending--;
    }
  }

  /** Apply the user's decision for one conflict. If the cloud moved on since the conflict was recorded, only the record is refreshed and nothing is overwritten. */
  async resolveConflict(path: string, resolution: string, content: string | undefined, signal?: AbortSignal): Promise<Record<string, unknown>> {
    const real = await realpath(this.root);
    if (active.has(real)) throw new TeamError('sync_busy');
    active.add(real);
    try {
      this.creds = await loadCredentials(this.root); this.dir = stateDir(real); this.manifest = await this.loadManifest();
      this.signal = signal; this.deadline = Date.now() + (this.options.budgetMs ?? 5000);
      this.client = new TeamClient(this.creds.serverUrl, this.creds.key);
      const conflict = await getConflict(this.dir, path);
      if (!conflict) throw new TeamError('no_such_conflict');
      const doc = await this.current(path);
      const cloudVersion = doc?.version ?? 0;
      if (cloudVersion !== conflict.remoteVersion) {
        const updated = await recordConflict(this.dir, { path, kind: conflict.kind, local: conflict.local, remote: doc?.content ?? null, baseVersion: conflict.baseVersion, remoteVersion: cloudVersion });
        return { status: 'cloud_changed', path, kind: updated.kind, remote: updated.remote, remoteVersion: cloudVersion };
      }
      if (resolution === 'keep_remote' || resolution === 'accept_delete') {
        if (!doc) throw new TeamError('cloud_document_missing');
        if (resolution === 'accept_delete' && doc.content !== null) throw new TeamError('cloud_not_deleted');
        const snap = await this.files.read(path);
        if (doc.content === null) { if (snap !== null) await this.files.remove(path, hash(snap)!); }
        else if (hash(snap) !== doc.hash) await this.files.write(path, doc.content, hash(snap));
        this.setEntry(path, doc.version, doc.hash);
      } else {
        const next = resolution === 'merged' ? content : conflict.local;
        if (resolution === 'merged' && typeof next !== 'string') throw new TeamError('content_required');
        const snap = await this.files.read(path);
        if (next === null || next === undefined) {
          if (snap !== null) await this.files.remove(path, hash(snap)!);
          const r = await this.request(this.docUrl(path), 'DELETE', undefined, { 'if-match': String(cloudVersion) });
          if (!Number.isSafeInteger(r.version) || r.version < 1) throw new TeamError('invalid_response');
          this.setEntry(path, r.version, null);
        } else {
          if (Buffer.byteLength(next) > MAX_SYNC_BYTES) throw new TeamError('document_too_large');
          if (hash(snap) !== hashContent(next)) await this.files.write(path, next, hash(snap));
          const r = await this.request(this.docUrl(path), 'PUT', { content: next }, { 'if-match': String(cloudVersion) });
          if (!Number.isSafeInteger(r.version) || r.version < 1 || r.hash !== hashContent(next)) throw new TeamError('invalid_response');
          this.setEntry(path, r.version, hashContent(next));
        }
      }
      await this.save();
      await clearConflict(this.dir, path);
      this.conflictCount = (await listConflicts(this.dir)).length;
      return { status: 'resolved', path, resolution, remainingConflicts: this.conflictCount };
    } finally { active.delete(real); }
  }

  /** Read-only: how many local changes are waiting and how many conflicts are unresolved. */
  async inspect(): Promise<SyncResult> {
    this.creds = await loadCredentials(this.root);
    this.dir = stateDir(await realpath(this.root));
    this.manifest = await this.loadManifest();
    const scan = await scanSyncFiles(this.root);
    let pending = 0;
    for (const path of new Set([...scan.files, ...Object.keys(this.manifest.entries)])) {
      if (planPush(this.entry(path), hash(await this.files.read(path))).action !== 'noop') pending++;
    }
    this.conflictCount = (await listConflicts(this.dir)).length;
    return { ...this.status(), pending };
  }

  async sync(force = false, signal?: AbortSignal): Promise<SyncResult> {
    const now = (this.options.now ?? Date.now)();
    if (this.halted && !force) return this.status(false);
    if (!force && now < this.nextAttempt) return this.status(false);
    const real = await realpath(this.root);
    if (active.has(real)) return this.status(false);
    active.add(real);
    try {
      this.creds = await loadCredentials(this.root);
      this.dir = stateDir(real);
      this.manifest = await this.loadManifest();
      this.workspace = { type: this.creds.workspaceType };
      this.signal = signal; this.deadline = Date.now() + (this.options.budgetMs ?? 1500); this.pending = 0;
      this.client = new TeamClient(this.creds.serverUrl, this.creds.key);
      await this.pull();
      await this.push();
      this.conflictCount = (await listConflicts(this.dir)).length;
      this.lastSyncAt = now; this.lastError = null; this.halted = null; this.failures = 0; this.nextAttempt = 0;
      return this.status(true);
    } catch (error) {
      const te = error instanceof TeamError ? error : null;
      this.lastError = te ? (te.status === 410 ? 'workspace_archived' : te.code) : error instanceof Error && /busy|symlink|collision|local_changed/iu.test(error.message) ? error.message : 'local_sync_failed';
      if (te && (te.status === 401 || te.status === 403 || te.status === 410)) this.halted = this.lastError;
      if (te && (['network_unavailable', 'budget_exhausted'].includes(te.code) || te.status >= 500)) this.nextAttempt = now + Math.min(120000, 15000 * 2 ** Math.min(this.failures++, 3));
      return this.status(false);
    } finally { active.delete(real); }
  }
}
