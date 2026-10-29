/**
 * One project owns exactly one `.vibe/` memory root at its top level. Sub-repositories,
 * worktrees and sub-directories share it. The memory root is therefore the nearest
 * ancestor (including the start directory itself) that already contains `.vibe/`.
 * When no ancestor has one, the start directory is the root: a fresh project.
 *
 * `isMemoryDirectory` is injected so the rule is testable without touching the disk.
 * Path handling is kept dependency-free so the core stays pure; both `/` and `\` separators work.
 */
export function parentDirectory(path: string): string {
  if (/^[A-Za-z]:[\\/]?$/.test(path)) return path.length === 2 ? `${path}\\` : path; // Windows drive root
  const trimmed = path.length > 1 ? path.replace(/[\\/]+$/, "") : path;
  const index = Math.max(trimmed.lastIndexOf("/"), trimmed.lastIndexOf("\\"));
  if (index < 0) return trimmed; // relative name without separator: no parent
  if (index === 0) return trimmed.slice(0, 1); // POSIX root "/"
  const parent = trimmed.slice(0, index);
  return /^[A-Za-z]:$/.test(parent) ? `${parent}\\` : parent; // Windows drive root "C:\"
}

export function resolveMemoryRoot(startDirectory: string, isMemoryDirectory: (candidate: string) => boolean): string {
  if (!startDirectory.trim()) throw new Error("startDirectory must not be empty");
  let current = startDirectory;
  for (;;) {
    if (isMemoryDirectory(current)) return current;
    const parent = parentDirectory(current);
    if (parent === current) return startDirectory;
    current = parent;
  }
}
