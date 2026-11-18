import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { createReadStream } from "node:fs";
import { lstat, realpath } from "node:fs/promises";
import { isAbsolute, relative, resolve, sep } from "node:path";

export interface ArtifactEvidence { root: string; paths: string[]; digest: string }

/** Explicit file scope. Missing files are represented for deletions; symlinks and directories fail closed. */
export async function fingerprintArtifacts(root: string, paths: string[]): Promise<ArtifactEvidence> {
  const canonical = await realpath(root);
  if (!Array.isArray(paths) || paths.length === 0 || paths.some(p => typeof p !== "string" || !p.trim() || isAbsolute(p) || p.includes("\\") || p.split("/").some(s => !s || s === "." || s === ".." || s === ".git"))) {
    throw new Error("Verification requires explicit, safe relative artifact file paths");
  }
  // Include changed tracked and nonignored untracked files in a Git workspace.
  // The explicit paths also cover unchanged dependencies and ignored artifacts.
  let gitRoot: string | undefined;
  const git = (args: string[]) => execFileSync("git", ["-C", canonical, ...args], { encoding: "utf8", timeout: 10000, maxBuffer: 32 * 1024 * 1024, stdio: ["ignore", "pipe", "ignore"] });
  try { gitRoot = git(["rev-parse", "--show-toplevel"]).trim(); } catch { /* non-Git workspace: explicit scope only */ }
  const all = new Set(paths);
  const hash = createHash("sha256");
  if (gitRoot && await realpath(gitRoot) === canonical) {
    let head: string;
    try { head = git(["rev-parse", "--verify", "HEAD"]).trim(); } catch { head = "unborn"; }
    hash.update(JSON.stringify(["HEAD", head]));
    const changed = [head === "unborn" ? git(["ls-files", "-z"]) : git(["diff", "--name-only", "--no-renames", "-z", "HEAD", "--"]), git(["ls-files", "--others", "--exclude-standard", "-z"])].join("");
    for (const path of changed.split("\0")) if (path && !path.startsWith(".vibe/tasks/") && !path.startsWith(".vibe/sessions/") && path !== ".vibe/progress.md") all.add(path);
  }
  const sorted = [...all].sort();
  for (const path of sorted) {
    if (isAbsolute(path) || path.includes("\\") || path.split("/").some(s => !s || s === "." || s === ".." || s === ".git")) throw new Error("Unsafe artifact path");
    if (path.startsWith(".vibe/tasks/") || path.startsWith(".vibe/sessions/")) throw new Error("Task and Session control records cannot be verification artifacts");
    const file = resolve(canonical, path);
    // Inspect every existing ancestor, including a missing file's parent, to reject symlink escapes.
    let current = canonical;
    for (const segment of path.split("/")) {
      current = resolve(current, segment);
      try { if ((await lstat(current)).isSymbolicLink()) throw new Error(`Symlink artifact: ${path}`); }
      catch (e) { if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e; }
    }
    let stat;
    try { stat = await lstat(file); } catch (e) { if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e; }
    if (!stat) { hash.update(JSON.stringify([path, "missing"])); continue; }
    if (!stat.isFile() || relative(canonical, await realpath(file)).startsWith(`..${sep}`)) throw new Error(`Not a regular artifact file: ${path}`);
    const content = createHash("sha256");
    for await (const chunk of createReadStream(file)) content.update(chunk);
    hash.update(JSON.stringify([path, stat.mode & 0o777, content.digest("hex")]));
  }
  return { root: canonical, paths: sorted, digest: hash.digest("hex") };
}

export async function evidenceCurrent(evidence: ArtifactEvidence): Promise<boolean> {
  try { return (await fingerprintArtifacts(evidence.root, evidence.paths)).digest === evidence.digest; }
  catch { return false; }
}
