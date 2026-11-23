import { layerOf, validateServerPath, type PathValidation } from "./layout.ts";

export type Projection =
  | { kind: "root"; relativePath: string }
  | { kind: "memory"; relativePath: string }
  | { kind: "unmapped"; relativePath: string; warn: true };

export type MirrorItem = { serverPath: string; local: Projection };

function assertValidPath(path: string): void {
  const result: PathValidation = validateServerPath(path);
  if (!result.ok) throw new Error(`invalid path: ${result.reason}`);
}

export function projectServerPath(path: string): Projection {
  assertValidPath(path);

  if (path === "constitution/AGENTS.md") {
    return { kind: "root", relativePath: "AGENTS.md" };
  }
  if (path.startsWith("constitution/skills/")) {
    const skillPath = path.slice("constitution/skills/".length);
    if (skillPath.length > 0 && !skillPath.startsWith("/")) {
      return { kind: "root", relativePath: `.opencode/skills/${skillPath}` };
    }
  }

  if (layerOf(path) !== undefined || path === "index.json") {
    return { kind: "memory", relativePath: path };
  }
  return { kind: "unmapped", relativePath: `_unmapped/${path}`, warn: true };
}

function validLocalPath(path: unknown): path is string {
  return validateServerPath(path).ok;
}

/** Convert a project-relative local path back to its authoritative server path. */
export function unprojectLocalPath(relativeToRoot: string): string | null {
  if (!validLocalPath(relativeToRoot)) return null;

  if (relativeToRoot === "AGENTS.md") return "constitution/AGENTS.md";
  if (relativeToRoot.startsWith(".opencode/skills/")) {
    const skillPath = relativeToRoot.slice(".opencode/skills/".length);
    if (skillPath.length === 0 || skillPath.startsWith("/")) return null;
    const serverPath = `constitution/skills/${skillPath}`;
    return projectServerPath(serverPath).kind === "root" ? serverPath : null;
  }

  if (!relativeToRoot.startsWith(".vibe/")) return null;
  const serverPath = relativeToRoot.slice(".vibe/".length);
  if (!validLocalPath(serverPath)) return null;

  const projection = projectServerPath(serverPath);
  if (projection.kind !== "memory" || projection.relativePath !== serverPath) return null;
  return serverPath;
}

export function buildMirrorPlan(paths: string[]): {
  batch: MirrorItem[];
  collisions: string[];
} {
  const batch = paths.map((serverPath) => ({
    serverPath,
    local: projectServerPath(serverPath),
  }));
  const seen = new Set<string>();
  const collisionSet = new Set<string>();
  for (const item of batch) {
    const key = `${item.local.kind}:${item.local.relativePath}`;
    if (seen.has(key)) collisionSet.add(key);
    seen.add(key);
  }
  return { batch, collisions: [...collisionSet] };
}
