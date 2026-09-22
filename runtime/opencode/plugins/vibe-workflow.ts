import { spawn, spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { homedir } from "node:os"
import { isAbsolute, join, relative, resolve } from "node:path"
import { type Plugin, tool } from "@opencode-ai/plugin"

const MAX_COMMAND_OUTPUT = 200_000
const MAX_INJECTED_CHARS = 8_000
const REFRESH_DEBOUNCE_MS = Number(process.env.VIBE_REFRESH_DEBOUNCE_MS ?? 750)
const COMMAND_TIMEOUT_MS = 20_000

const VIBE_COMMAND = "python"
const WRITE_TOOLS = new Set(["write", "edit", "patch", "apply_patch", "multiedit", "notebookedit"])
const SHELL_TOOLS = new Set(["bash", "shell", "command", "terminal"])

type CliResult = { code: number; stdout: string; stderr: string }
type Runtime = { root: string; python: string; script: string }

function truncate(value: string, limit = MAX_INJECTED_CHARS): string {
  if (value.length <= limit) return value
  return `${value.slice(0, limit)}\n...[truncated by vibe-workflow plugin]`
}

function resolveRuntime(directory: string, worktree: string): Runtime | null {
  const configDir =
    process.env.OPENCODE_CONFIG_DIR ?? join(process.env.XDG_CONFIG_HOME ?? join(homedir(), ".config"), "opencode")
  const root = existsSync(join(directory, ".project-log")) ? directory : worktree
  if (!existsSync(join(root, ".project-log"))) return null

  const candidates = [
    process.env.VIBE_RUNTIME_SCRIPT,
    process.env.VIBE_RUNTIME ? join(process.env.VIBE_RUNTIME, "scripts", "vibe.py") : undefined,
    join(configDir, "vibe-workflow", "scripts", "vibe.py"),
    join(homedir(), ".codex", "vibe-workflow", "scripts", "vibe.py"),
  ].filter((value): value is string => typeof value === "string" && value.length > 0)
  const script = candidates.find((candidate) => existsSync(candidate))
  if (!script) return null

  let python = process.env.VIBE_PYTHON
  for (const pointer of [join(configDir, "vibe-python"), join(homedir(), ".codex", "vibe-python")]) {
    if (python) break
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

function detectPython(): string {
  for (const candidate of ["python3", "python"]) {
    try {
      const probe = spawnSync(candidate, ["-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"], {
        stdio: "ignore",
        timeout: 2_000,
      })
      if (probe.status === 0) return candidate
    } catch {
      // try the next candidate
    }
  }
  return VIBE_COMMAND
}

function runCli(runtime: Runtime, args: string[], timeoutMs = COMMAND_TIMEOUT_MS): Promise<CliResult> {
  return new Promise((resolveResult) => {
    const child = spawn(runtime.python, [runtime.script, "--root", runtime.root, ...args], {
      cwd: runtime.root,
      stdio: ["ignore", "pipe", "pipe"],
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

export const VibeWorkflowPlugin: Plugin = async ({ directory, worktree, client }) => {
  const runtime = resolveRuntime(directory, worktree)
  let refreshTimer: ReturnType<typeof setTimeout> | undefined
  let refreshInFlight = false
  let scheduledReasons = new Set<string>()
  let pendingReasons = new Set<string>()

  const log = async (level: "info" | "warn" | "error", message: string, extra?: Record<string, unknown>) => {
    await client.app
      .log({ body: { service: "vibe-workflow", level, message, extra: { directory, ...extra } } })
      .catch(() => undefined)
  }

  const refreshState = async (reason: string) => {
    if (!runtime) return
    if (refreshInFlight) {
      pendingReasons.add(reason)
      return
    }
    refreshInFlight = true
    try {
      const result = await runCli(runtime, ["evidence", "refresh", "--reason", reason])
      if (result.code !== 0) {
        await log("warn", "vibe evidence refresh failed", {
          exit: result.code,
          detail: truncate(result.stderr || result.stdout, 1_000),
        })
      }
    } finally {
      refreshInFlight = false
      if (pendingReasons.size > 0) {
        const queued = [...pendingReasons]
        pendingReasons = new Set()
        void refreshState(queued.join("; "))
      }
    }
  }

  const scheduleRefresh = (reason: string) => {
    if (!runtime) return
    scheduledReasons.add(reason)
    if (refreshTimer) clearTimeout(refreshTimer)
    refreshTimer = setTimeout(() => {
      refreshTimer = undefined
      const reasons = [...scheduledReasons]
      scheduledReasons = new Set()
      void refreshState(reasons.join("; "))
    }, REFRESH_DEBOUNCE_MS)
    refreshTimer.unref?.()
  }

  const stateContext = async (sessionID?: string): Promise<string> => {
    if (!runtime) {
      return [
        "## Vibe Workflow State",
        "No Vibe runtime was resolved for this project (install the OpenCode runtime or set VIBE_RUNTIME_SCRIPT).",
        "Do not assume project state.",
      ].join("\n")
    }
    const { status, note } = await readState(runtime)
    const body = status === null ? note || "vibe status returned no parseable JSON state." : JSON.stringify(status, null, 2)
    return [
      "## Vibe Workflow State",
      "Authoritative state comes from `.project-log` through the `vibe` runtime; this block is a bounded read-only snapshot.",
      sessionID ? `session: ${sessionID}` : "",
      truncate(body),
    ]
      .filter(Boolean)
      .join("\n")
  }

  if (!runtime) {
    await log("warn", "Vibe Workflow plugin loaded without a resolvable runtime; hooks stay inactive")
  } else {
    await log("info", "Vibe Workflow plugin initialized", { root: runtime.root, script: runtime.script })
  }

  return {
    "experimental.chat.system.transform": async (input, output) => {
      if (!runtime) {
        output.system.push(
          "## Vibe Workflow State\nNo Vibe runtime was resolved for this project; run the OpenCode installer or set VIBE_RUNTIME_SCRIPT. Do not assume project state.",
        )
        return
      }
      try {
        output.system.push(await stateContext(input.sessionID))
      } catch (error) {
        await log("warn", "state injection failed", { detail: String(error) })
      }
    },

    "experimental.session.compacting": async (input, output) => {
      if (!runtime) {
        output.context.push(
          "No Vibe runtime was resolved for this project; preserve the goal, tasks, blockers and next action verbatim from the conversation.",
        )
        return
      }
      try {
        const refreshed = await runCli(runtime, ["state-views"])
        if (refreshed.code !== 0) {
          await log("warn", "view refresh before compaction failed", {
            exit: refreshed.code,
            detail: truncate(refreshed.stderr || refreshed.stdout, 1_000),
          })
        }
        output.context.push(await stateContext(input.sessionID))
        output.context.push(
          [
            "Preserve the active Project Goal, open tasks, blockers, valid evidence, files being changed,",
            "and the exact next action. Never promote an assumption to a confirmed fact, and never",
            "claim completion that the evidence gate has not allowed.",
          ].join(" "),
        )
      } catch (error) {
        await log("warn", "compaction context injection failed", { detail: String(error) })
      }
    },

    "tool.execute.after": async (input) => {
      if (!runtime) return
      try {
        const tool = input.tool.toLowerCase()
        if (!WRITE_TOOLS.has(tool) && !SHELL_TOOLS.has(tool)) return
        const paths = writtenPaths(input.args)
          .map((value) => normalizeToolPath(runtime.root, value))
          .filter((value): value is string => value !== null)
        scheduleRefresh(
          paths.length > 0
            ? `tool ${input.tool} modified ${paths.join(", ")}`
            : `tool ${input.tool} may have modified project files`,
        )
      } catch (error) {
        await log("warn", "post-write refresh scheduling failed", { detail: String(error) })
      }
    },

    tool: {
      vibe_workflow_status: tool({
        description:
          "Read the authoritative Vibe Coding project state (Project Goal, tasks, runs, blockers, evidence) without modifying the project.",
        args: {
          taskID: tool.schema.string().optional().describe("Optional task id for bounded task context"),
        },
        async execute(args) {
          if (!runtime) {
            return "No Vibe runtime was resolved for this project. Install the OpenCode runtime or set VIBE_RUNTIME_SCRIPT."
          }
          const command = args.taskID ? ["context", args.taskID] : ["status"]
          const result = await runCli(runtime, command)
          if (result.code !== 0) {
            return `vibe ${command.join(" ")} failed (exit ${result.code}): ${truncate(
              result.stderr || result.stdout,
              4_000,
            )}`
          }
          return truncate(result.stdout, 16_000)
        },
      }),
    },
  }
}

export default VibeWorkflowPlugin
