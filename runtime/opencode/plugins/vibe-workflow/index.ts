// Vibe Workflow plugin for OpenCode V2.
//
// OpenCode V2 loads a plugin directory whose default export is a definition with an
// `id` and a `setup(ctx)` function. The installer places this directory at
// `<config>/plugins/vibe-workflow/`, where OpenCode discovers it automatically, so the
// plugin is deliberately not listed in `opencode.json` (listing it as well loads it twice).
//
// Hooks used (all documented V2 plugin APIs):
//   ctx.session.hook("context")      inject a bounded, read-only project state snapshot
//   ctx.session.hook("compaction")   refresh generated views and keep state across compaction
//   ctx.tool.hook("execute.after")   schedule `vibe evidence refresh` after file-writing tools
//   ctx.tool.transform(editor.add)   register the read-only `vibe_workflow_status` tool
//
// The project root is resolved on every call instead of once at setup: a plugin instance
// outlives the moment `.project-log/` is created, and a session can live in a different
// directory than the instance location.
import { spawn, spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { homedir } from "node:os"
import { isAbsolute, join, relative, resolve } from "node:path"
import { Plugin } from "@opencode/plugin"

const MAX_COMMAND_OUTPUT = 200_000
const MAX_INJECTED_CHARS = 8_000
const REFRESH_DEBOUNCE_MS = Number(process.env.VIBE_REFRESH_DEBOUNCE_MS ?? 750)
const COMMAND_TIMEOUT_MS = 20_000
const SESSION_DIRECTORY_CACHE_LIMIT = 256

const VIBE_COMMAND = "python"
const WRITE_TOOLS = new Set(["write", "edit", "patch", "apply_patch", "multiedit", "notebookedit"])
const SHELL_TOOLS = new Set(["bash", "shell", "command", "terminal"])
const NO_RUNTIME_TEXT =
  "## Vibe Workflow State\nNo Vibe runtime was resolved for this project; run the OpenCode installer or set VIBE_RUNTIME_SCRIPT. Do not assume project state."

type CliResult = { code: number; stdout: string; stderr: string }
type Runtime = { root: string; python: string; script: string }
type TextPart = { type: "text"; text: string }
type Location = { directory?: string; project?: { directory?: string; canonical?: string } }
type SessionInfo = { location?: { directory?: string } }

function truncate(value: string, limit = MAX_INJECTED_CHARS): string {
  if (value.length <= limit) return value
  return `${value.slice(0, limit)}\n...[truncated by vibe-workflow plugin]`
}

function configDir(): string {
  return (
    process.env.OPENCODE_CONFIG_DIR ?? join(process.env.XDG_CONFIG_HOME ?? join(homedir(), ".config"), "opencode")
  )
}

function detectPython(): string {
  for (const candidate of ["python3", "python"]) {
    try {
      const probe = spawnSync(candidate, ["-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"], {
        stdio: "ignore",
        timeout: 2_000,
        windowsHide: true,
      })
      if (probe.status === 0) return candidate
    } catch {
      // try the next candidate
    }
  }
  return VIBE_COMMAND
}

function resolveRuntime(directories: readonly (string | undefined)[]): Runtime | null {
  const root = directories.find(
    (candidate): candidate is string =>
      typeof candidate === "string" && candidate.length > 0 && existsSync(join(candidate, ".project-log")),
  )
  if (!root) return null

  const dir = configDir()
  const scripts = [
    process.env.VIBE_RUNTIME_SCRIPT,
    process.env.VIBE_RUNTIME ? join(process.env.VIBE_RUNTIME, "scripts", "vibe.py") : undefined,
    join(dir, "vibe-workflow", "scripts", "vibe.py"),
  ].filter((value): value is string => typeof value === "string" && value.length > 0)
  const script = scripts.find((candidate) => existsSync(candidate))
  if (!script) return null

  let python = process.env.VIBE_PYTHON
  if (!python) {
    const pointer = join(dir, "vibe-python")
    if (existsSync(pointer)) {
      try {
        python = readFileSync(pointer, "utf8").trim()
      } catch {
        python = undefined
      }
    }
  }
  if (!python) python = detectPython()
  return { root, python: python || VIBE_COMMAND, script }
}

function cliEnvironment(): NodeJS.ProcessEnv {
  // The runtime is self-contained. A foreign PYTHONPATH (for example a ROS install that
  // points at another Python's site-packages) can shadow its dependencies, so drop it.
  const environment: NodeJS.ProcessEnv = { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" }
  delete environment.PYTHONPATH
  return environment
}

function runCli(runtime: Runtime, args: string[], timeoutMs = COMMAND_TIMEOUT_MS): Promise<CliResult> {
  return new Promise((resolveResult) => {
    const child = spawn(runtime.python, [runtime.script, "--root", runtime.root, ...args], {
      cwd: runtime.root,
      env: cliEnvironment(),
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    })
    let stdout = ""
    let stderr = ""
    let settled = false

    const finish = (code: number) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      resolveResult({ code, stdout, stderr })
    }
    const timer = setTimeout(() => {
      child.kill("SIGKILL")
      finish(-1)
    }, timeoutMs)
    timer.unref?.()
    child.stdout?.on("data", (chunk: Buffer | string) => {
      if (stdout.length < MAX_COMMAND_OUTPUT) stdout += chunk.toString()
    })
    child.stderr?.on("data", (chunk: Buffer | string) => {
      if (stderr.length < MAX_COMMAND_OUTPUT) stderr += chunk.toString()
    })
    child.on("error", (error) => {
      stderr += `${error.message}\n`
      finish(-1)
    })
    child.on("close", (code) => finish(code ?? -1))
  })
}

function parseStatus(stdout: string): unknown {
  try {
    return JSON.parse(stdout)
  } catch {
    return null
  }
}

async function readState(runtime: Runtime): Promise<{ status: unknown; note: string }> {
  // `vibe status` prints JSON on stdout; it has no --json flag.
  const result = await runCli(runtime, ["status"])
  if (result.code !== 0) {
    return {
      status: null,
      note: `vibe status failed (exit ${result.code}); output: ${truncate(result.stderr || result.stdout, 2_000)}`,
    }
  }
  return { status: parseStatus(result.stdout), note: "" }
}

function normalizeToolPath(root: string, value: string): string | null {
  if (!value) return null
  const absolute = isAbsolute(value) ? resolve(value) : resolve(root, value)
  const relativePath = relative(root, absolute).replaceAll("\\", "/")
  if (!relativePath || relativePath.startsWith("..")) return null
  return relativePath
}

function writtenPaths(args: unknown): string[] {
  if (!args || typeof args !== "object") return []
  const record = args as Record<string, unknown>
  const values = [record.filePath, record.file_path, record.path, record.file, record.target]
  if (Array.isArray(record.paths)) values.push(...record.paths)
  return values.filter((value): value is string => typeof value === "string" && value.length > 0)
}

export default Plugin.define({
  id: "vibe-workflow",
  async setup(ctx) {
    const location = ((ctx as { location?: Location }).location ?? {}) as Location
    const sessionApi = (ctx as { session?: { get?: (input: { sessionID: string }) => Promise<SessionInfo> } }).session
    const sessionDirectories = new Map<string, string | undefined>()

    const sessionDirectory = async (sessionID?: string): Promise<string | undefined> => {
      if (!sessionID || typeof sessionApi?.get !== "function") return undefined
      if (sessionDirectories.has(sessionID)) return sessionDirectories.get(sessionID)
      let directory: string | undefined
      try {
        directory = (await sessionApi.get({ sessionID }))?.location?.directory
      } catch {
        directory = undefined
      }
      if (sessionDirectories.size >= SESSION_DIRECTORY_CACHE_LIMIT) sessionDirectories.clear()
      sessionDirectories.set(sessionID, directory)
      return directory
    }

    // Re-resolved on every call so a `.project-log/` created after setup is picked up.
    const runtimeFor = async (sessionID?: string): Promise<Runtime | null> =>
      resolveRuntime([
        await sessionDirectory(sessionID),
        location.directory,
        location.project?.directory,
        location.project?.canonical,
      ])

    let refreshTimer: ReturnType<typeof setTimeout> | undefined
    const refreshInFlight = new Set<string>()
    const scheduled = new Map<string, { runtime: Runtime; reasons: Set<string> }>()
    const pending = new Map<string, { runtime: Runtime; reasons: Set<string> }>()

    const log = (level: "info" | "warn" | "error", message: string, extra?: Record<string, unknown>) => {
      const sink = level === "info" ? console.log : level === "warn" ? console.warn : console.error
      sink(`[vibe-workflow] ${message}`, extra ? JSON.stringify(extra) : "")
    }

    const refreshState = async (runtime: Runtime, reason: string): Promise<void> => {
      if (refreshInFlight.has(runtime.root)) {
        const queued = pending.get(runtime.root) ?? { runtime, reasons: new Set<string>() }
        queued.reasons.add(reason)
        pending.set(runtime.root, queued)
        return
      }
      refreshInFlight.add(runtime.root)
      try {
        const result = await runCli(runtime, ["evidence", "refresh", "--reason", reason])
        if (result.code !== 0) {
          log("warn", "vibe evidence refresh failed", {
            exit: result.code,
            detail: truncate(result.stderr || result.stdout, 1_000),
          })
        }
      } finally {
        refreshInFlight.delete(runtime.root)
        const queued = pending.get(runtime.root)
        if (queued) {
          pending.delete(runtime.root)
          void refreshState(queued.runtime, [...queued.reasons].join("; "))
        }
      }
    }

    const scheduleRefresh = (runtime: Runtime, reason: string) => {
      const entry = scheduled.get(runtime.root) ?? { runtime, reasons: new Set<string>() }
      entry.reasons.add(reason)
      scheduled.set(runtime.root, entry)
      if (refreshTimer) clearTimeout(refreshTimer)
      refreshTimer = setTimeout(() => {
        refreshTimer = undefined
        const batches = [...scheduled.values()]
        scheduled.clear()
        for (const batch of batches) void refreshState(batch.runtime, [...batch.reasons].join("; "))
      }, REFRESH_DEBOUNCE_MS)
      refreshTimer.unref?.()
    }

    const memoryContext = (runtime: Runtime): string =>
      ([
        ["current-session.md", 3500],
        ["progress.md", 2000],
      ] as const)
        .map(([name, limit]) => {
          try {
            const text = readFileSync(join(runtime.root, ".project-log", name), "utf8")
            return `### ${name} (Agent-maintained; verify against authoritative task state)\n${truncate(text, limit)}`
          } catch {
            return `### ${name}\nUnavailable; run \`vibe init\` or restore the note from the ledger.`
          }
        })
        .join("\n\n")

    const stateContext = async (runtime: Runtime, sessionID?: string): Promise<string> => {
      const { status, note } = await readState(runtime)
      const body =
        status === null ? note || "vibe status returned no parseable JSON state." : JSON.stringify(status, null, 2)
      return [
        "## Vibe Workflow State",
        "Authoritative state comes from `.project-log` through the `vibe` runtime; this block is a bounded read-only snapshot.",
        sessionID ? `session: ${sessionID}` : "",
        truncate(body, 3000),
        "",
        "## Agent Project Memory",
        memoryContext(runtime),
        "Update these notes with `vibe memory sync --file <json>` at task completion, blockage, handoff or before compaction; structured facts still go to SQLite and the ledger.",
      ]
        .filter(Boolean)
        .join("\n")
    }

    const initial = await runtimeFor()
    log("info", "Vibe Workflow plugin initialized", {
      directory: location.directory,
      root: initial?.root ?? null,
      script: initial?.script ?? null,
    })

    await ctx.session.hook("context", async (event) => {
      try {
        const runtime = await runtimeFor(event.sessionID)
        event.system.push({
          type: "text",
          text: runtime ? await stateContext(runtime, event.sessionID) : NO_RUNTIME_TEXT,
        } satisfies TextPart)
      } catch (error) {
        log("warn", "state injection failed", { detail: String(error) })
      }
    })

    await ctx.session.hook("compaction", async (event) => {
      try {
        const runtime = await runtimeFor(event.sessionID)
        if (!runtime) {
          event.system.push({
            type: "text",
            text: "No Vibe runtime was resolved for this project; preserve the goal, tasks, blockers and next action verbatim from the conversation.",
          } satisfies TextPart)
          return
        }
        const refreshed = await runCli(runtime, ["state-views"])
        if (refreshed.code !== 0) {
          log("warn", "view refresh before compaction failed", {
            exit: refreshed.code,
            detail: truncate(refreshed.stderr || refreshed.stdout, 1_000),
          })
        }
        event.system.push({ type: "text", text: await stateContext(runtime, event.sessionID) } satisfies TextPart)
        event.system.push({
          type: "text",
          text: [
            "Preserve the active Project Goal, open tasks, blockers, valid evidence, files being changed,",
            "and the exact next action. Never promote an assumption to a confirmed fact, and never",
            "claim completion that the evidence gate has not allowed.",
          ].join(" "),
        } satisfies TextPart)
      } catch (error) {
        log("warn", "compaction context injection failed", { detail: String(error) })
      }
    })

    // The V2 event carries { tool, sessionID, input, status, result | error }.
    await ctx.tool.hook("execute.after", async (event) => {
      try {
        const record = event as unknown as { tool?: unknown; sessionID?: string; input?: unknown; status?: unknown }
        // A failed write or shell call may still have changed files part-way, so failures
        // also refresh evidence; only tools that cannot write are skipped.
        const toolName = String(record.tool ?? "").toLowerCase()
        if (!WRITE_TOOLS.has(toolName) && !SHELL_TOOLS.has(toolName)) return
        const runtime = await runtimeFor(record.sessionID)
        if (!runtime) return
        const paths = writtenPaths(record.input)
          .map((value) => normalizeToolPath(runtime.root, value))
          .filter((value): value is string => value !== null)
        scheduleRefresh(
          runtime,
          paths.length > 0
            ? `tool ${toolName} modified ${paths.join(", ")}`
            : `tool ${toolName} may have modified project files`,
        )
      } catch (error) {
        log("warn", "post-write refresh scheduling failed", { detail: String(error) })
      }
    })

    await ctx.tool.transform((editor) => {
      editor.add({
        name: "vibe_workflow_status",
        description:
          "Read the authoritative Vibe Coding project state (Project Goal, tasks, runs, blockers, evidence) without modifying the project.",
        input: {
          type: "object",
          properties: {
            taskID: { type: "string", description: "Optional task id for bounded task context" },
          },
          additionalProperties: false,
        },
        execute: async (args, context) => {
          const sessionID = (context as { sessionID?: string } | undefined)?.sessionID
          const runtime = await runtimeFor(sessionID)
          if (!runtime) {
            return {
              content:
                "No Vibe runtime was resolved for this project. Install the OpenCode runtime or set VIBE_RUNTIME_SCRIPT.",
            }
          }
          const record = (args ?? {}) as { taskID?: unknown }
          const command = record.taskID ? ["context", String(record.taskID)] : ["status"]
          const result = await runCli(runtime, command)
          if (result.code !== 0) {
            return {
              content: `vibe ${command.join(" ")} failed (exit ${result.code}): ${truncate(
                result.stderr || result.stdout,
                4_000,
              )}`,
            }
          }
          return { content: truncate(result.stdout, 16_000) }
        },
      })
    })
  },
})
