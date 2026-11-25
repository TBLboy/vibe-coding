// Pure hash-route parsing, kept free of DOM access so it can be tested directly.

export const TAB_KEYS = ["overview", "log", "members"];

export function parseRoute(hash) {
  const [rawPath, rawQuery = ""] = (String(hash ?? "").replace(/^#/, "") || "/").split("?");
  let parts;
  try {
    parts = rawPath.split("/").filter(Boolean).map(decodeURIComponent);
  } catch {
    return { name: "unknown" };
  }
  const [head, second, third] = parts;
  if (parts.length === 0) return { name: "root" };
  if (head === "login" && parts.length === 1) return { name: "login" };
  if (head === "workspaces" && parts.length === 1) return { name: "workspaces" };
  if (head === "invitations" && parts.length === 2) return { name: "invitation", workspaceId: second };
  if (head === "w" && parts.length === 2) return { name: "workspace", workspaceId: second, tab: "overview", path: null };
  if (head === "w" && parts.length === 3 && TAB_KEYS.includes(third)) {
    return { name: "workspace", workspaceId: second, tab: third, path: new URLSearchParams(rawQuery).get("path") };
  }
  return { name: "unknown" };
}
