import { randomUUID } from "node:crypto";
import { realpath } from "node:fs/promises";
import { resolve } from "node:path";
import type { HostContext } from "./host-contract.ts";
import {
  MODES,
  buildModeCommandPrompt,
  isMode,
  isPendingModeChange,
  modeStorageKey,
  normalizeMode,
  pendingModeStorageKey,
  renderModeInstructions,
} from "../../../core/mode.ts";
import { activeTaskStorageKey, isTaskPointer } from "../../../core/review-authorization.ts";
import { resolveMemoryRoot } from "../../../core/memory-root.ts";
import { createTaskController } from "./task-control.ts";
import { statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { shouldEnableTeamModules } from "./team/gate.ts";

export async function setup(ctx: HostContext) {
    const hasMemoryDirectory = (candidate: string): boolean => {
      try {
        return statSync(resolve(candidate, ".vibe")).isDirectory();
      } catch {
        return false;
      }
    };

    const workspaceFor = async (sessionID: string): Promise<string | null> => {
      try {
        const info = await ctx.session.get({ sessionID }) as unknown as { directory?: string; location?: { directory?: string } };
        const directory = info.directory ?? info.location?.directory;
        if (!directory) return null;
        const cwd = await realpath(directory);
        try { return await realpath(execFileSync("git", ["-C", cwd, "rev-parse", "--show-toplevel"], { encoding: "utf8", timeout: 5000, windowsHide: true, stdio: ["ignore", "pipe", "ignore"] }).trim()); }
        catch { return resolveMemoryRoot(cwd, hasMemoryDirectory); }
      } catch { return null; }
    };
    const memoryRootFor = async (sessionID: string): Promise<string | null> => {
      const workspace = await workspaceFor(sessionID);
      if (!workspace) return null;
      try {
        const common = execFileSync("git", ["-C", workspace, "rev-parse", "--path-format=absolute", "--git-common-dir"], { encoding: "utf8", timeout: 5000, windowsHide: true, stdio: ["ignore", "pipe", "ignore"] }).trim();
        const canonical = resolve(common, "..");
        if (hasMemoryDirectory(canonical)) return await realpath(canonical);
      } catch { /* non-Git projects keep ancestor resolution */ }
      return resolveMemoryRoot(workspace, hasMemoryDirectory);
    };
    const controller = createTaskController({
      storage: { get: key => ctx.storage.get(key), set: async (key, value) => { await ctx.storage.set(key, JSON.parse(JSON.stringify(value))); }, remove: key => ctx.storage.remove(key) },
      memoryRoot: memoryRootFor, workspace: workspaceFor,
      childSession: async sessionID => await ctx.session.get({ sessionID }) as { parentID?: string; agent?: string; outcome?: string },
      childContext: sessionID => ctx.session.context({ sessionID }),
    });

    await ctx.command.transform((editor) => {
      for (const mode of MODES) {
        editor.add({
          name: mode,
          description: `Switch this Session to ${mode} mode. Optional trailing text is executed as the task.`,
          execute: async ({ sessionID, prompt }) => {
            const token = randomUUID();
            await ctx.storage.set(pendingModeStorageKey(sessionID, token), { mode, token, consumed: false });
            const taskText = typeof prompt.text === "string" ? prompt.text.trim() : "";
            const text = buildModeCommandPrompt(mode, taskText, Boolean(prompt.files?.length), token);
            // Queue the mode command so it cannot interrupt the currently running action.
            await ctx.session.prompt({ ...prompt, sessionID, text, delivery: "queue" });
          },
        });
      }
    });

    await ctx.tool.transform((editor) => {
      editor.add({
        name: "vibe_set_session_mode",
        description: "Consume a one-time mode-change token created by an explicit /fast, /balanced, or /strict command. Never use this tool for ordinary user text.",
        input: {
          type: "object",
          properties: {
            mode: { type: "string", enum: [...MODES] },
            token: { type: "string", minLength: 1 },
          },
          required: ["mode", "token"],
          additionalProperties: false,
        },
        execute: async (input, context) => {
          if (context.agent !== "vibe-main") return { content: "Rejected: only vibe-main can change Session mode." };
          const requestedMode: unknown = input.mode;
          const token = typeof input.token === "string" ? input.token : "";
          if (!isMode(requestedMode) || !token) {
            return { content: "Rejected: invalid mode-change request." };
          }

          const key = pendingModeStorageKey(context.sessionID, token);
          const pending: unknown = await ctx.storage.get(key);
          if (!isPendingModeChange(pending, requestedMode, token)) {
            return { content: "Rejected: no matching unused token from an explicit mode command. The Session mode was not changed." };
          }

          // Remove first so a storage failure cannot leave a replayable token.
          await ctx.storage.remove(key);
          await ctx.storage.set(modeStorageKey(context.sessionID), requestedMode);
          return { content: `Session mode changed to ${requestedMode}.` };
        },
      });

      editor.add({
        name: "vibe_task_control",
        description: "Runtime-owned persistent Task lifecycle. Start a fresh prepare JSON, then use transition events; never edit registered Task JSON directly. See docs/03-STATE-MACHINE.md.",
        input: { type: "object", properties: {
          action: { type: "string", enum: ["start", "resume", "resume_blocked", "pause", "close", "authorize_review", "reset_review", "transition"] },
          taskID: { type: "string", minLength: 1 }, event: { type: "object", additionalProperties: true },
        }, required: ["action", "taskID"], additionalProperties: false },
        execute: async (input, context) => {
          try { return { content: await controller.control(input, { sessionID: context.sessionID, agent: context.agent }) }; }
          catch (error) { return { content: `Rejected: ${error instanceof Error ? error.message : String(error)}` }; }
        },
      });
    });

    await ctx.permission.hook("evaluate", async (event) => {
      if (event.action !== "subagent" || !event.resources.includes("vibe-reviewer")) return;
      let allowed = false;
      try {
        const source = event.source;
        const call = source?.type === "tool" && source.messageID && source.id ? { messageID: source.messageID, id: source.id } : undefined;
        allowed = await controller.admit(event.sessionID, event.agent, call);
      } catch { /* fail closed */ }
      event.effect = allowed ? "allow" : "deny";
      event.message = allowed ? "One-time strict review permit consumed; verdict is not yet recorded." : "Reviewer invocation denied: no current authorized strict review.";
    });

    await ctx.tool.hook("execute.after", async event => {
      if (event.tool !== "subagent" || event.status !== "completed") return;
      try {
        await controller.complete(event.sessionID, event.agent, { messageID: event.messageID, id: event.id }, event.input, event.result?.output);
      } catch { /* malformed, stale or failed result leaves the Task pending; main must inspect and reset explicitly */ }
    });

    await ctx.session.hook("context", async (event) => {
      try { await controller.reconcile(event.sessionID); }
      catch {
        event.system.push({ type: "text", text: "Strict reviewer result could not be accepted. Read the active Task; inspect the host result and reset the pending review before retrying. Never submit a verdict yourself." });
      }
      const storedMode: unknown = await ctx.storage.get(modeStorageKey(event.sessionID));
      const mode = isMode(storedMode) ? storedMode : normalizeMode(storedMode);
      const pointer: unknown = await ctx.storage.get(activeTaskStorageKey(event.sessionID));
      const memoryRoot = await memoryRootFor(event.sessionID);
      event.system.push({
        type: "text",
        text: renderModeInstructions(mode, event.sessionID, {
          memoryRoot: memoryRoot ?? undefined,
          activeTask: isTaskPointer(pointer) ? pointer : undefined,
        }),
      });
    });

    // No binding: no team registrations, writes or network. Initial connection is
    // an explicit local CLI operation, not a globally exposed bootstrap tool.
    if(ctx.location?.directory) {
      let root=resolveMemoryRoot(await realpath(ctx.location.directory),hasMemoryDirectory);
      const canonical=ctx.location.project?.canonical;
      if(canonical&&hasMemoryDirectory(canonical))root=await realpath(canonical);
      if(await shouldEnableTeamModules(root)) {
        const {setupTeam}=await import("./team/setup-team.ts");
        await setupTeam(ctx,root,memoryRootFor);
      }
    }
}
