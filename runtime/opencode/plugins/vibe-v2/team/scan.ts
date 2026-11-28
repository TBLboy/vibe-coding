import { lstat, readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { SafeFiles } from "./files.ts";
import { decodeText, pathsCollide, MAX_DOCUMENT_BYTES } from "../../../../../shared/team-contracts/limits.ts";
import { validateSyncPath } from '../../../../../shared/team-contracts/layout.ts';

export const MAX_SYNC_BYTES = MAX_DOCUMENT_BYTES;
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
      if (!s.isFile()) { warnings.push(`skipped (not regular): ${rel}`); return; }
      size = s.size;
    } catch (error) { if (missing(error)) return; throw error; }
    if (size > MAX_SYNC_BYTES) { warnings.push(`skipped (over 1 MiB): ${rel}`); return; }
    let bytes:Buffer|null;
    try{bytes=await new SafeFiles(root).read(rel);}catch(e){warnings.push(`skipped (unsafe filesystem path): ${rel}`);return;}
    if (bytes === null) return;
    try { decodeText(bytes); }
    catch { warnings.push(`skipped (not UTF-8 text): ${rel}`); return; }
    files.push(rel);
  };
  const walk = async (rel: string): Promise<void> => {
    check();
    let entries;
    try { const s = await lstat(absolute(root, rel)); if (!s.isDirectory() || s.isSymbolicLink()) {warnings.push(`skipped (not regular directory): ${rel}`);return;} entries = await readdir(absolute(root, rel), { withFileTypes: true }); }
    catch (error) { if (missing(error)) return; throw error; }
    for (const entry of entries.sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0))) {
      const child = `${rel}/${entry.name}`;
      if (entry.name.startsWith('.tmp-')) continue;
      if (child.toLowerCase() === '.vibe/.sync') continue;
      if (!validateSyncPath(child).ok) { warnings.push(`skipped (invalid path): ${child}`); continue; }
      if (entry.isSymbolicLink()) { warnings.push(`skipped (symlink): ${child}`); continue; }
      if (entry.isDirectory()) await walk(child); else await consider(child);
    }
  };
  await consider('AGENTS.md');
  await walk('.vibe');
  files.sort();
  for(const path of files)if(files.some(other=>pathsCollide(path,other)))throw new Error("case collision in local sync paths");
  return { files, warnings };
}
