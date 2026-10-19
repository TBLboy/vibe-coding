import { randomUUID } from "node:crypto";
import { readFile, realpath } from "node:fs/promises";
import { sep, resolve } from "node:path";
import { Plugin } from "@opencode/plugin";
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
import {
  activeTaskStorageKey,
  canAuthorizeReview,
  canCloseTask,
  isActiveTaskPointer,
  isTaskPointer,
  isReviewPermit,
  reviewPermitStorageKey,
} from "../../../core/review-authorization.ts";

const TASK_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/;

export default Plugin.define({
  id: "vibe-coding-v2",
  async setup(ctx) {
    const loadTask = async (sessionID: string, taskID: string): Promise<unknown | null> => {
      if (!TASK_ID_PATTERN.test(taskID)) return null;
      try {
        const sessionInfo: unknown = await ctx.session.get({ sessionID });
        if (!sessionInfo || typeof sessionInfo !== "object") return null;
        const sessionRecord = sessionInfo as { directory?: unknown; location?: { directory?: unknown } };
        const directory = typeof sessionRecord.directory === "string"
          ? sessionRecord.directory
          : typeof sessionRecord.location?.directory === "string"
            ? sessionRecord.location.directory
            : "";
        if (!directory) return null;
        const projectRoot = await realpath(directory);
        const taskDirectory = await realpath(resolve(projectRoot, ".vibe", "tasks"));
        const taskPath = await realpath(resolve(taskDirectory, `${taskID}.json`));
        if (!taskPath.startsWith(`${taskDirectory}${sep}`)) return null;
        return JSON.parse(await readFile(taskPath, "utf8")) as unknown;
      } catch {
        return null;
      }
    };

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
        description: "Maintain the per-Session pointer for a persistent Task. Use only at Task start/resume/block/finish/cancel; this is control state, not an operation log.",
        input: {
          type: "object",
          properties: {
            action: { type: "string", enum: ["start", "resume", "pause", "close", "authorize_review"] },
            taskID: { type: "string", minLength: 1 },
          },
          required: ["action", "taskID"],
          additionalProperties: false,
        },
        execute: async (input, context) => {
          const action = input.action;
          const taskID = typeof input.taskID === "string" ? input.taskID : "";
          if (!TASK_ID_PATTERN.test(taskID)) return { content: "Rejected: invalid Task ID." };

          const task = await loadTask(context.sessionID, taskID);
          if (!task || typeof task !== "object") {
            return { content: "Rejected: the persisted Task file could not be read. No control state changed." };
          }
          const record = task as { id?: unknown; policy?: unknown; status?: unknown; phase?: unknown; verification?: { status?: unknown }; review?: { verdict?: unknown } };
          if (record.id !== taskID) return { content: "Rejected: Task ID does not match the persisted Task file." };

          const activeKey = activeTaskStorageKey(context.sessionID);
          const activeValue: unknown = await ctx.storage.get(activeKey);
          const pointer = isTaskPointer(activeValue) ? activeValue : undefined;
          const active = pointer?.active ? pointer : undefined;
          const permitKey = reviewPermitStorageKey(context.sessionID);

          if (action === "start") {
            const currentMode = normalizeMode(await ctx.storage.get(modeStorageKey(context.sessionID)));
            if (record.status !== "active" || !isMode(record.policy) || record.policy !== currentMode) {
              return { content: "Rejected: a new Task must be active and its frozen policy must match the current Session mode." };
            }
            if (active && active.taskID !== taskID) {
              return { content: `Rejected: Task ${active.taskID} is already active in this Session. Resume, pause, or close it first.` };
            }
            if (pointer && pointer.taskID === taskID && pointer.policy !== record.policy) {
              return { content: "Rejected: the Task policy differs from the frozen policy already registered for this Task." };
            }
            if (pointer && pointer.taskID === taskID && !pointer.active) {
              return { content: "Rejected: this Task is paused; use action=resume instead of starting it again." };
            }
            await ctx.storage.set(activeKey, { taskID, policy: record.policy, active: true });
            return { content: `Task ${taskID} is registered as the active Task for this Session.` };
          }

          if (action === "resume") {
            if (record.status !== "active" || !isMode(record.policy)) {
              return { content: "Rejected: update the persisted Task to active with a valid frozen policy after resolving its blocker before resuming it." };
            }
            if (active && active.taskID !== taskID) {
              return { content: `Rejected: Task ${active.taskID} is already active in this Session.` };
            }
            if (pointer && pointer.taskID === taskID && pointer.policy !== record.policy) {
              return { content: "Rejected: the Task policy differs from the frozen policy already registered for this Task." };
            }
            await ctx.storage.set(activeKey, { taskID, policy: record.policy, active: true });
            return { content: `Task ${taskID} is active again. Its original policy remains frozen.` };
          }

          if (action === "pause") {
            if (record.status !== "blocked") {
              return { content: "Rejected: only a blocked Task can be paused." };
            }
            if (active && active.taskID !== taskID) {
              return { content: `Rejected: Task ${active.taskID} is active in this Session.` };
            }
            if (!isMode(record.policy) || (pointer && pointer.taskID === taskID && pointer.policy !== record.policy)) {
              return { content: "Rejected: Task policy does not match the registered frozen policy." };
            }
            await ctx.storage.set(activeKey, { taskID, policy: record.policy, active: false });
            const pendingPermit: unknown = await ctx.storage.get(permitKey);
            if (isReviewPermit(pendingPermit, taskID)) await ctx.storage.remove(permitKey);
            return { content: `Blocked Task ${taskID} is paused; its persisted state is preserved.` };
          }

          if (action === "close") {
            if (!canCloseTask(task, taskID)) {
              return { content: "Rejected: only a valid completed or cancelled Task can be closed. Completed Tasks require verification; strict Tasks also require review go." };
            }
            if (active && active.taskID !== taskID) {
              return { content: `Rejected: Task ${active.taskID} is active in this Session.` };
            }
            if (pointer && pointer.taskID === taskID && pointer.policy !== record.policy) {
              return { content: "Rejected: Task policy does not match the registered frozen policy." };
            }
            await ctx.storage.set(activeKey, { taskID, policy: record.policy as "fast" | "balanced" | "strict", active: false });
            const permit: unknown = await ctx.storage.get(permitKey);
            if (isReviewPermit(permit, taskID)) await ctx.storage.remove(permitKey);
            return { content: `Task ${taskID} is closed.` };
          }

          if (action === "authorize_review") {
            if (!isActiveTaskPointer(activeValue, taskID) || activeValue.policy !== "strict") {
              return { content: "Rejected: only the active strict Task for this Session can request review authorization." };
            }
            if (!canAuthorizeReview(task, taskID)) {
              return { content: "Rejected: reviewer authorization requires an active strict Task in review phase, passed verification, and a pending review verdict." };
            }
            const existingPermit: unknown = await ctx.storage.get(permitKey);
            if (isReviewPermit(existingPermit, taskID)) {
              return { content: `A reviewer permit is already pending for Task ${taskID}; invoke vibe-reviewer now.` };
            }
            if (isReviewPermit(existingPermit)) await ctx.storage.remove(permitKey);
            await ctx.storage.set(permitKey, { taskID, consumed: false });
            return { content: `One-time reviewer permit issued for strict Task ${taskID}. Invoke vibe-reviewer now.` };
          }

          return { content: "Rejected: unknown Task control action." };
        },
      });
    });

    await ctx.permission.hook("evaluate", async (event) => {
      if (event.action !== "subagent" || !event.resources.includes("vibe-reviewer")) return;
      const activeValue: unknown = await ctx.storage.get(activeTaskStorageKey(event.sessionID));
      const permitKey = reviewPermitStorageKey(event.sessionID);
      const permit: unknown = await ctx.storage.get(permitKey);
      if (!isActiveTaskPointer(activeValue) || activeValue.policy !== "strict" || !isReviewPermit(permit, activeValue.taskID)) {
        event.effect = "deny";
        event.message = "Reviewer invocation denied: only an active strict Task in review phase may invoke the reviewer.";
        return;
      }

      const task = await loadTask(event.sessionID, activeValue.taskID);
      if (!canAuthorizeReview(task, activeValue.taskID)) {
        await ctx.storage.remove(permitKey);
        event.effect = "deny";
        event.message = "Reviewer invocation denied: the persisted Task is no longer ready for review.";
        return;
      }

      await ctx.storage.remove(permitKey);
      event.effect = "allow";
      event.message = `One-time strict review permit consumed for Task ${activeValue.taskID}.`;
    });

    await ctx.session.hook("context", async (event) => {
      const storedMode: unknown = await ctx.storage.get(modeStorageKey(event.sessionID));
      const mode = isMode(storedMode) ? storedMode : normalizeMode(storedMode);
      event.system.push({
        type: "text",
        text: renderModeInstructions(mode, event.sessionID),
      });
    });
  },
});
