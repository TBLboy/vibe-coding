import { lstat, readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { validateSyncPath } from '../../../../../shared/team-contracts/layout.ts';

export const MAX_SYNC_BYTES = 1024 * 1024;
export interface ScanResult { files: string[]; warnings: string[] }

const absolute = (root: string, rel: string): string => join(root, ...rel.split('/'));
const missing = (error: unknown): boolean => (error as NodeJS.ErrnoException)?.code === 'ENOENT';

/** Sync scope: AGENTS.md plus every regular file under .vibe/ except .vibe/.sync/. Unsyncable files are skipped with a warning; the round never aborts. */
export async function scanSyncFiles(root: string, check: () => void = () => {}): Promise<ScanResult> {
  const files: string[] = [], warnings: string[] = [];
  const consider = async (rel: string): Promise<void> => {
    if (rel.split('/').at(-1)!.startsWith('.tmp-')) return;
    if (!validateSyncPath(rel).ok) { warnings.push(`skipped (invalid path): ${rel}`); return; }
    let size: number;
    try {
      const s = await lstat(absolute(root, rel));
      if (s.isSymbolicLink()) { warnings.push(`skipped (symlink): ${rel}`); return; }
      if (!s.isFile()) return;
      size = s.size;
    } catch (error) { if (missing(error)) return; throw error; }
    if (size > MAX_SYNC_BYTES) { warnings.push(`skipped (over 1 MiB): ${rel}`); return; }
    const bytes = await readFile(absolute(root, rel));
    try { new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
    catch { warnings.push(`skipped (not UTF-8 text): ${rel}`); return; }
    files.push(rel);
  };
  const walk = async (rel: string): Promise<void> => {
    check();
    let entries;
    try { entries = await readdir(absolute(root, rel), { withFileTypes: true }); }
    catch (error) { if (missing(error)) return; throw error; }
    for (const entry of entries.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))) {
      const child = `${rel}/${entry.name}`;
      if (child === '.vibe/.sync') continue;
      if (entry.isSymbolicLink()) { warnings.push(`skipped (symlink): ${child}`); continue; }
      if (entry.isDirectory()) await walk(child); else await consider(child);
    }
  };
  await consider('AGENTS.md');
  await walk('.vibe');
  files.sort();
  return { files, warnings };
}
