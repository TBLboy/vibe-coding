import { engineeringDev, type TemplatePack } from "./engineering-dev/index.ts";

export const DEFAULT_TYPE = "engineering-dev";

const PACKS: Record<string, TemplatePack> = { [engineeringDev.type]: engineeringDev };

/** Unknown types return undefined; the API maps that to 422 unsupported_type. */
export function getTemplate(type: string): TemplatePack | undefined {
  return Object.hasOwn(PACKS, type) ? PACKS[type] : undefined;
}

export function listTypes(): string[] {
  return Object.keys(PACKS);
}
