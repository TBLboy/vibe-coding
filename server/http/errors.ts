export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message); this.name = "ApiError";
    this.status = status; this.code = code; this.details = details;
  }
}

export function invalid(message: string): never { throw new ApiError(422, "validation_failed", message); }
export function unauthenticated(): never { throw new ApiError(401, "unauthenticated", "Invalid or expired credentials"); }
export function forbidden(): never { throw new ApiError(403, "forbidden", "Access denied"); }
export function notFound(): never { throw new ApiError(404, "not_found", "Not found"); }
export function conflict(message: string): never { throw new ApiError(409, "conflict", message); }

export function bodyObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) invalid("Expected an object");
  return value as Record<string, unknown>;
}
export function text(value: unknown, field: string, max: number): string {
  if (typeof value !== "string" || !value.trim() || value.length > max || /[\u0000-\u001f\u007f]/u.test(value)) invalid(`Invalid ${field}`);
  return value.trim();
}
