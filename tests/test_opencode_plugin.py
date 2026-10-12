"""TASK-071: OpenCode V2 plugin and hook integration."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "runtime/opencode/plugins/vibe-workflow/index.ts"
NODE = shutil.which("node")
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from _platform import make_opencode_plugin_node_modules  # noqa: E402


def node_strips_types() -> bool:
    """Node imports a .ts plugin only when it can strip TypeScript types (22.18+)."""
    if NODE is None:
        return False
    probe = subprocess.run(
        [NODE, "--no-warnings", "--input-type=module", "-e",
         "const v = process.versions.node.split('.').map(Number);"
         "process.exit(v[0] > 22 || (v[0] === 22 && v[1] >= 18) ? 0 : 1)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return probe.returncode == 0


# A stub of the V2 plugin context: it records registered hooks and tools so the
# probe can drive them exactly as OpenCode would.
PROBE_PRELUDE = r"""
import definition from $plugin_url
import { mkdirSync, readFileSync } from "node:fs"

const hooks = { session: {}, tool: {} }
const tools = {}
const ctx = {
  location: { directory: $location, project: { id: "p", directory: $location, canonical: $location } },
  session: {
    hook: async (name, callback) => { hooks.session[name] = callback; return { dispose: async () => {} } },
    get: async ({ sessionID }) => ({ id: sessionID, location: { directory: $session_directory } }),
  },
  tool: {
    hook: async (name, callback) => { hooks.tool[name] = callback; return { dispose: async () => {} } },
    transform: async (callback) => {
      callback({ add: (tool) => { tools[tool.name] = tool } })
      return { dispose: async () => {} }
    },
  },
}
const text = (parts) => parts.map((part) => part.text).join("\n")
"""

PROBE = PROBE_PRELUDE + r"""
if (definition.id !== "vibe-workflow" || typeof definition.setup !== "function") {
  throw new Error("plugin must default-export { id, setup }")
}
await definition.setup(ctx)

const context = { sessionID: "probe-session", system: [], messages: [], options: {}, tools: {} }
await hooks.session.context(context)
const compaction = { sessionID: "probe-session", system: [], messages: [], options: {} }
await hooks.session.compaction(compaction)
const status = await tools.vibe_workflow_status.execute({}, { sessionID: "probe-session" })
await hooks.tool["execute.after"]({
  tool: "write", sessionID: "probe-session", id: "c1", status: "completed",
  input: { filePath: "src/app.py" }, result: { content: [] },
})
await hooks.tool["execute.after"]({
  tool: "shell", sessionID: "probe-session", id: "c2", status: "completed",
  input: { command: "touch src/app.py" }, result: { content: [] },
})
await hooks.tool["execute.after"]({
  tool: "read", sessionID: "probe-session", id: "c3", status: "completed",
  input: { filePath: "src/app.py" }, result: { content: [] },
})

const logPath = $log_path
for (let attempt = 0; attempt < 60; attempt += 1) {
  try {
    if (readFileSync(logPath, "utf8").includes("refresh")) break
  } catch {}
  await new Promise((resolve) => setTimeout(resolve, 50))
}
await new Promise((resolve) => setTimeout(resolve, 100))

process.stdout.write(JSON.stringify({
  sessionHooks: Object.keys(hooks.session).sort(),
  toolHooks: Object.keys(hooks.tool).sort(),
  tools: Object.keys(tools).sort(),
  systemInjected: context.system.length === 1 && text(context.system).includes("TASK-001"),
  compactionInjected: compaction.system.length === 2 && compaction.system[0].text.includes("TASK-001"),
  statusOutput: status.content,
}))
"""

LATE_PROBE = PROBE_PRELUDE + r"""
await definition.setup(ctx)
const before = { sessionID: "late-session", system: [], messages: [], options: {}, tools: {} }
await hooks.session.context(before)
mkdirSync($late_log, { recursive: true })
const after = { sessionID: "late-session", system: [], messages: [], options: {}, tools: {} }
await hooks.session.context(after)
process.stdout.write(JSON.stringify({ before: text(before.system), after: text(after.system) }))
"""


def write_stub_runtime(root: Path) -> Path:
    runtime = root / "runtime"
    (runtime / "scripts").mkdir(parents=True)
    stub = runtime / "scripts/vibe.py"
    stub.write_text(
        "import json, os, pathlib, sys\n"
        "log = pathlib.Path(__file__).resolve().parents[2] / 'invocations.jsonl'\n"
        "with log.open('a') as handle:\n"
        "    handle.write(json.dumps({'argv': sys.argv[1:], 'pythonpath': os.environ.get('PYTHONPATH')}) + '\\n')\n"
        "print(json.dumps({'current_task': {'id': 'TASK-001', 'status': 'in-progress'}}))\n",
        encoding="utf-8",
    )
    return stub


def run_probe(root: Path, source: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    probe = root / "probe.mjs"
    probe.write_text(source, encoding="utf-8")
    return subprocess.run(
        [str(NODE), "--no-warnings", str(probe)],
        env=environment, cwd=root, text=True, errors="replace", stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=False, timeout=90,
    )


def plugin_copy(root: Path) -> Path:
    make_opencode_plugin_node_modules(root)
    target = root / "plugins" / "vibe-workflow" / "index.ts"
    target.parent.mkdir(parents=True)
    shutil.copy2(PLUGIN, target)
    return target


class OpenCodePluginSourceTests(unittest.TestCase):
    def test_plugin_uses_the_v2_api_and_avoids_unsafe_actions(self) -> None:
        text = PLUGIN.read_text(encoding="utf-8")
        for required in (
            'from "@opencode/plugin"',
            "Plugin.define(",
            'id: "vibe-workflow"',
            'ctx.session.hook("context"',
            'ctx.session.hook("compaction"',
            'ctx.tool.hook("execute.after"',
            "ctx.tool.transform(",
            "vibe_workflow_status",
            "truncate(",
            "spawn(",
            "scheduleRefresh(",
            "delete environment.PYTHONPATH",
        ):
            self.assertIn(required, text)
        # Every console child must be hidden: on Windows an un-hidden python.exe
        # flashes a console window on each hook and tool call (ALIGN-FW-003).
        spawn_calls = text.count("spawn(") + text.count("spawnSync(")
        self.assertEqual(
            text.count("windowsHide: true"),
            spawn_calls,
            "every spawn/spawnSync call must set windowsHide: true",
        )
        for forbidden in (
            "@opencode-ai/plugin",
            "experimental.chat.system.transform",
            "exec(",
            "execSync",
            "shell: true",
            "task.finish",
            "goal complete",
            "writeFile",
            "unlink",
            "rm -rf",
        ):
            self.assertNotIn(forbidden, text)

    def test_v1_single_file_plugin_is_gone(self) -> None:
        self.assertFalse((ROOT / "runtime/opencode/plugins/vibe-workflow.ts").exists())
        self.assertEqual(
            sorted(path.name for path in (ROOT / "runtime/opencode/plugins").iterdir()),
            ["vibe-workflow"],
        )


@unittest.skipUnless(node_strips_types(), "Node.js 22.18+ is required to import the TypeScript plugin")
class OpenCodePluginTests(unittest.TestCase):
    def test_plugin_loads_and_bridges_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = plugin_copy(root)
            stub = write_stub_runtime(root)
            project = root / "project"
            (project / ".project-log").mkdir(parents=True)
            log_path = root / "invocations.jsonl"
            source = Template(PROBE).substitute(
                plugin_url=json.dumps(plugin.as_uri()),
                location=json.dumps(str(project)),
                session_directory=json.dumps(str(project)),
                log_path=json.dumps(str(log_path)),
            )
            environment = os.environ.copy()
            environment.update({
                "VIBE_RUNTIME_SCRIPT": str(stub),
                "VIBE_PYTHON": sys.executable,
                "VIBE_REFRESH_DEBOUNCE_MS": "50",
                "OPENCODE_CONFIG_DIR": str(root / "config"),
                "PYTHONPATH": str(root / "foreign-site-packages"),
            })
            result = run_probe(root, source, environment)
            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(payload["sessionHooks"], ["compaction", "context"])
            self.assertEqual(payload["toolHooks"], ["execute.after"])
            self.assertEqual(payload["tools"], ["vibe_workflow_status"])
            self.assertTrue(payload["systemInjected"])
            self.assertTrue(payload["compactionInjected"])
            self.assertIn("TASK-001", payload["statusOutput"])

            rows = [
                json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            invocations = [row["argv"] for row in rows]
            self.assertIn(["--root", str(project), "state-views"], invocations)
            self.assertIn(["--root", str(project), "status"], invocations)
            refreshes = [row for row in invocations if row[2:4] == ["evidence", "refresh"]]
            self.assertEqual(len(refreshes), 1, invocations)
            reason = " ".join(refreshes[0])
            self.assertIn("--reason", refreshes[0])
            self.assertIn("src/app.py", reason)
            self.assertIn("shell", reason)
            self.assertNotIn("read", reason)
            # A foreign PYTHONPATH must not leak into runtime calls.
            self.assertEqual({row["pythonpath"] for row in rows}, {None})

    def test_project_log_created_after_setup_is_picked_up(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = plugin_copy(root)
            stub = write_stub_runtime(root)
            instance = root / "instance"
            instance.mkdir()
            project = root / "project"
            project.mkdir()
            source = Template(LATE_PROBE).substitute(
                plugin_url=json.dumps(plugin.as_uri()),
                # The plugin instance location has no project log; the session lives elsewhere.
                location=json.dumps(str(instance)),
                session_directory=json.dumps(str(project)),
                late_log=json.dumps(str(project / ".project-log")),
            )
            environment = os.environ.copy()
            environment.update({
                "VIBE_RUNTIME_SCRIPT": str(stub),
                "VIBE_PYTHON": sys.executable,
                "OPENCODE_CONFIG_DIR": str(root / "config"),
            })
            result = run_probe(root, source, environment)
            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertIn("No Vibe runtime was resolved", payload["before"])
            self.assertIn("TASK-001", payload["after"])

    def test_plugin_degrades_safely_without_a_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugin = plugin_copy(root)
            project = root / "project"
            (project / ".project-log").mkdir(parents=True)
            source = Template(PROBE_PRELUDE).substitute(
                plugin_url=json.dumps(plugin.as_uri()),
                location=json.dumps(str(project)),
                session_directory=json.dumps(str(project)),
            ) + (
                "await definition.setup(ctx)\n"
                "const event = { sessionID: 's', system: [], messages: [], options: {}, tools: {} }\n"
                "await hooks.session.context(event)\n"
                "const status = await tools.vibe_workflow_status.execute({}, { sessionID: 's' })\n"
                "process.stdout.write(JSON.stringify({ system: text(event.system), status: status.content }))\n"
            )
            environment = os.environ.copy()
            for key in ("VIBE_RUNTIME_SCRIPT", "VIBE_RUNTIME", "VIBE_PYTHON"):
                environment.pop(key, None)
            environment.update({
                "HOME": str(root / "home"),
                # node:os homedir() ignores HOME on Windows and reads USERPROFILE,
                # so pin it too or the probe would resolve the real installed runtime.
                "USERPROFILE": str(root / "home"),
                "OPENCODE_CONFIG_DIR": str(root / "config"),
            })
            result = run_probe(root, source, environment)
            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertIn("No Vibe runtime was resolved", payload["system"])
            self.assertIn("No Vibe runtime was resolved", payload["status"])


if __name__ == "__main__":
    unittest.main()
