export interface Binding {
  workspaceId: string;
  serverUrl: string;
  accountId: string;
}

const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u;

function assertId(value: unknown, field: "workspaceId" | "accountId"): asserts value is string {
  if (typeof value !== "string" || !ID_PATTERN.test(value)) {
    throw new Error(`invalid ${field}`);
  }
}

function normalizeServerUrl(value: unknown): string {
  if (typeof value !== "string" || value.length === 0) throw new Error("invalid serverUrl");
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw new Error("invalid serverUrl");
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new Error("invalid serverUrl");
  if (url.search || url.hash || url.username || url.password) throw new Error("invalid serverUrl");

  const pathname = url.pathname === "/" ? "" : url.pathname;
  return `${url.origin}${pathname}`;
}

export function validateBinding(value: unknown): Binding {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("invalid binding");
  }
  const candidate = value as Record<string, unknown>;
  assertId(candidate.workspaceId, "workspaceId");
  assertId(candidate.accountId, "accountId");
  return {
    workspaceId: candidate.workspaceId,
    serverUrl: normalizeServerUrl(candidate.serverUrl),
    accountId: candidate.accountId,
  };
}

export function assertCanBind(existing: Binding | null, next: Binding): void {
  const candidate = validateBinding(next);
  if (existing === null) return;
  const current = validateBinding(existing);
  if (current.workspaceId !== candidate.workspaceId) {
    throw new Error("directory is already bound to another workspace");
  }
}
