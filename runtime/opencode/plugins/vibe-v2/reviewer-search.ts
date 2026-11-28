import { constants, type Stats } from "node:fs";
import { lstat, open, opendir, realpath } from "node:fs/promises";
import { resolve, relative, isAbsolute, sep } from "node:path";

// A bounded locator, not a command runner or a secret scanner. Return only
// paths/line numbers; native read remains the actual content access path.
const PROTECTED_DIRS = new Set([".git", ".ssh", ".aws", ".gnupg", ".config", ".kube", ".docker", "secrets", "credentials"]);
const SKIP_DIRS = new Set([".opencode", "node_modules", ".venv", "venv", "__pycache__", ".cache", "dist", "build", "coverage"]);
const MAX_ENTRIES = 10000, MAX_FILE = 512 * 1024, MAX_BYTES = 24 * 1024 * 1024, MAX_MATCHES = 100, MAX_TEXT_FILES = 1000;
const protectedName = (name: string) => {
  const n = name.toLowerCase();
  return PROTECTED_DIRS.has(n) || n === ".env" || n.startsWith(".env.") ||
    [".npmrc", ".pypirc", ".netrc", ".git-credentials", "auth.json", "opencode.json", "opencode.jsonc", "credentials.json", "id_rsa", "id_ed25519", "id_dsa", "id_ecdsa"].includes(n) ||
    /^service-account.*\.json$/.test(n) || /\.(pem|key|p12|pfx|jks|kdbx)$/.test(n);
};
// Defense in depth for host read permission events, not a complete secret
// detector. Generated files may still be directly read if otherwise authorized.
export const isProtectedReviewResource = (path: string) => path.replaceAll("\\", "/").split("/").some(protectedName);
const blocked = (s: string) => protectedName(s) || SKIP_DIRS.has(s.toLowerCase()) || /\.(sqlite[23]?|db)$/i.test(s);
const safeSegment = (s: string) => s.length > 0 && s !== "." && s !== ".." && !/[\\:\x00-\x1f\x7f]/.test(s) && !/[. ]$/.test(s) && !blocked(s);
const inside = (root: string, path: string) => { const rel = relative(root, path); return rel !== ".." && !rel.startsWith(`..${sep}`) && !isAbsolute(rel); };

export async function searchReviewWorkspace(root: string, input: Record<string, unknown>, signal?: AbortSignal, artifacts: readonly string[] = [], authorize: (paths: string[]) => Promise<void> = async () => {}) {
  const { kind, query, scope = "." } = input;
  signal?.throwIfAborted();
  if (Object.keys(input).some(k => !["kind", "query", "scope"].includes(k)) || (kind !== "files" && kind !== "text" && kind !== "artifacts") || (query !== undefined && (typeof query !== "string" || !query.trim() || query.length > 200 || /[\x00-\x1f\x7f]/.test(query))) || (kind !== "artifacts" && typeof query !== "string") || typeof scope !== "string" || scope.length > 512 || (scope !== "." && (isAbsolute(scope) || !scope.split("/").every(safeSegment)))) throw new Error("Expected artifacts/files/text, a literal query for files/text, and a safe project-relative scope");
  const needle = typeof query === "string" ? query : "";
  if (kind === "artifacts") {
    const safe = artifacts.filter(p => p.length <= 1024 && !isAbsolute(p) && p.split("/").every(safeSegment));
    const selected = safe.filter(p => (scope === "." || p === scope || p.startsWith(scope + "/")) && p.includes(needle));
    const paths = selected.slice(0, MAX_MATCHES);
    if (paths.length) await authorize(paths);
    signal?.throwIfAborted();
    return { kind, matches: paths.map(path => ({ path })), skipped: artifacts.length - safe.length, truncated: selected.length > MAX_MATCHES, note: "Runtime verification artifact inventory (explicit paths and observed Git changes when available); not a live diff or proof of complete coverage. Narrow scope/query if truncated." };
  }
  const canonical = await realpath(root);
  if (canonical !== root || (await lstat(root)).isSymbolicLink()) throw new Error("Unsafe workspace root");
  let start = root;
  if (scope !== ".") for (const segment of scope.split("/")) {
    start = resolve(start, segment);
    const info = await lstat(start);
    if (info.isSymbolicLink() || await realpath(start) !== start || !inside(root, start)) throw new Error("Unsafe search scope");
  }
  const matches: { path: string; line?: number }[] = [];
  const candidates: { path: string; name: string; stat: Stats }[] = [];
  let entries = 0, bytes = 0, skipped = 0, truncated = false;
  const capped = () => { signal?.throwIfAborted(); return entries >= MAX_ENTRIES || bytes >= MAX_BYTES || candidates.length >= MAX_TEXT_FILES || matches.length >= MAX_MATCHES; };
  async function walk(path: string): Promise<void> {
    if (capped()) { truncated = true; return; }
    entries++;
    let info;
    try { info = await lstat(path); if (info.isSymbolicLink() || await realpath(path) !== path || !inside(root, path)) { skipped++; return; } }
    catch { skipped++; return; }
    if (info.isDirectory()) {
      try {
        const dir = await opendir(path);
        for await (const item of dir) {
          if (capped()) { truncated = true; break; }
          if (!safeSegment(item.name) || item.isSymbolicLink()) { entries++; skipped++; continue; }
          await walk(resolve(path, item.name));
        }
      } catch { signal?.throwIfAborted(); skipped++; }
      return;
    }
    if (!info.isFile() || info.nlink !== 1) { skipped++; return; }
    const name = relative(root, path).split(sep).join("/");
    if (name.length > 1024) { skipped++; truncated = true; return; }
    if (kind === "files") { if (name.includes(needle)) matches.push({ path: name }); return; }
    if (info.size === 0) return;
    if (info.size > MAX_FILE || info.size > MAX_BYTES - bytes) { skipped++; if (info.size <= MAX_FILE) truncated = true; return; }
    bytes += info.size;
    candidates.push({ path, name, stat: info });
  }
  await walk(start);
  if (kind === "files" && matches.length) await authorize(matches.map(m => m.path));
  // Permission checks precede content reads, in bounded batches. A denial
  // aborts the call, rather than exposing even partial results for denied paths.
  for (let i = 0; i < candidates.length; i += 64) {
    signal?.throwIfAborted();
    const batch = candidates.slice(i, i + 64);
    await authorize(batch.map(c => c.name));
    for (const { path, name, stat: info } of batch) {
      if (matches.length >= MAX_MATCHES) { truncated = true; break; }
      signal?.throwIfAborted();
      try {
        if (await realpath(path) !== path) { skipped++; continue; }
        // No following final symlinks or blocking on substituted FIFOs; check
        // open identity before reading. Not an OS sandbox against hostile races.
        const file = await open(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
        try {
          const stat = await file.stat();
          if (!stat.isFile() || stat.nlink !== 1 || stat.dev !== info.dev || stat.ino !== info.ino || stat.size !== info.size || await realpath(path) !== path) { skipped++; continue; }
          const buffer = Buffer.alloc(stat.size);
          let offset = 0;
          while (offset < buffer.length) { signal?.throwIfAborted(); const { bytesRead } = await file.read(buffer, offset, buffer.length - offset, offset); if (!bytesRead) break; offset += bytesRead; }
          if (offset !== buffer.length || (await file.stat()).size !== stat.size || buffer.includes(0)) { skipped++; continue; }
          let text: string;
          try { text = new TextDecoder("utf-8", { fatal: true }).decode(buffer); } catch { skipped++; continue; }
          for (const [index, line] of text.split(/\r?\n/).entries()) {
            if (line.includes(needle)) { matches.push({ path: name, line: index + 1 }); if (matches.length >= MAX_MATCHES) { truncated = true; break; } }
          }
        } finally { await file.close(); }
      } catch { signal?.throwIfAborted(); skipped++; }
    }
    if (matches.length >= MAX_MATCHES) { truncated = true; break; }
  }
  signal?.throwIfAborted();
  return { kind, matches, scannedEntries: entries, skipped, truncated, note: "Literal search; protected, generated, linked, nonregular or unreadable entries may be omitted; text search also omits binary/oversized files. Read relevant files with native read. Absence is not proof of absence." };
}
