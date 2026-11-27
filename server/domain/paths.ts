import { validateServerPath } from "../../shared/team-contracts/layout.ts";

export type WorkspacePathCheck = { ok: true; path: string } | { ok: false; reason: string };

/** Synced paths are AGENTS.md and anything under .vibe/, except the device-private .vibe/.sync/. */
export function validateWorkspacePath(path: unknown): WorkspacePathCheck {
  const base = validateServerPath(path);
  if (!base.ok) return base;
  const p = base.path;
  if (p === "AGENTS.md") return { ok: true, path: p };
  if (!p.startsWith(".vibe/")) return { ok: false, reason: "path must be AGENTS.md or under .vibe/" };
  if (p.startsWith(".vibe/.sync/")) return { ok: false, reason: "path is device-private" };
  return { ok: true, path: p };
}
