/** Minimal documented host surface used by the adapter. This is not the SDK;
 * index.ts requires real SDK compatibility validation before rollout. */
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
export interface HostContext {
  location?: {directory:string;project?:{canonical?:string}};
  storage: { get(key: string): Promise<unknown>; set(key: string, value: JsonValue): Promise<void>; remove(key: string): Promise<void> };
  command: { transform(cb: (editor: { add(definition: CommandDefinition): void }) => void): Promise<unknown> };
  tool: { transform(cb: (editor: { add(definition: ToolDefinition): void }) => void): Promise<unknown>; hook(name: "execute.after", cb: (event: ToolAfterEvent) => Promise<void>): Promise<unknown> };
  session: {
    get(input: { sessionID: string }): Promise<unknown>;
    context(input: { sessionID: string }): Promise<readonly unknown[]>;
    prompt(input: CommandPrompt & { sessionID: string; text: string; delivery: "queue" }): Promise<unknown>;
    hook(name: "context", cb: (event: { sessionID: string; system: { type: "text"; text: string }[] }) => Promise<void>): Promise<unknown>;
  };
  permission: { hook(name: "evaluate", cb: (event: PermissionEvent) => Promise<void>): Promise<unknown> };
}
export interface CommandPrompt { text?: string; files?: unknown[]; [key: string]: unknown }
export interface CommandDefinition { name: string; description: string; execute(input: { sessionID: string; prompt: CommandPrompt }): Promise<void> }
export interface ToolDefinition { name: string; description: string; input: Record<string, unknown>; execute(input: Record<string, unknown>, context: { sessionID: string; agent?: string; signal?:AbortSignal }): Promise<{ content: string }> }
export interface PermissionEvent { action: string; resources: readonly string[]; sessionID: string; agent?: string; source?: { type: string; messageID?: string; id?: string }; effect: "allow" | "ask" | "deny"; message?: string }

export interface ToolAfterEvent { tool: string; sessionID: string; agent: string; messageID: string; id: string; input: unknown; status: "completed" | "error"; result?: { output?: unknown; content?: unknown; metadata?: unknown } }
