"""TASK-071: OpenCode plugin and hook integration."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "runtime/opencode/plugins/vibe-workflow.ts"
GLOBAL_NODE_MODULES = Path(os.environ.get("OPENCODE_NODE_MODULES", Path.home() / ".config/opencode/node_modules"))
NODE = shutil.which("node")
PLUGIN_PACKAGE = GLOBAL_NODE_MODULES / "@opencode-ai/plugin/package.json"

PROBE = r"""
import { VibeWorkflowPlugin } from $plugin_url
import { readFileSync } from "node:fs"

const noop = async () => ({})
const hooks = await VibeWorkflowPlugin({
  directory: $project,
  worktree: $project,
  client: { app: { log: noop } },
})

const output = { system: [] }
await hooks["experimental.chat.system.transform"]?.({ model: {} }, output)
const compact = { context: [] }
await hooks["experimental.session.compacting"]?.({ sessionID: "probe-session" }, compact)
const status = await hooks.tool.vibe_workflow_status.execute({}, {})
await hooks["tool.execute.after"](
  { tool: "write", sessionID: "probe-session", callID: "probe-call", args: { filePath: "src/app.py" } },
  {},
)
await hooks["tool.execute.after"](
  { tool: "bash", sessionID: "probe-session", callID: "probe-call-2", args: { command: "touch src/app.py" } },
  {},
)

const logPath = $log_path
for (let attempt = 0; attempt < 40; attempt += 1) {
  try {
    if (readFileSync(logPath, "utf8").trim().split("\n").length >= 2) break
  } catch {}
  await new Promise((resolve) => setTimeout(resolve, 50))
}
await new Promise((resolve) => setTimeout(resolve, 50))

process.stdout.write(JSON.stringify({
  hookNames: Object.keys(hooks).sort(),
  systemInjected: output.system.length === 1 && output.system[0].includes("TASK-001"),
  compactionInjected: compact.context.length === 2 && compact.context[0].includes("TASK-001"),
  statusOutput: status,
}))
"""


@unittest.skipUnless(NODE, "Node.js is required for the OpenCode plugin test")
@unittest.skipUnless(PLUGIN_PACKAGE.is_file(), "the global @opencode-ai/plugin package is required")
class OpenCodePluginTests(unittest.TestCase):
    def test_plugin_declares_bounded_hooks_and_avoids_unsafe_actions(self) -> None:
        text = PLUGIN.read_text(encoding="utf-8")
        for required in (
            '"experimental.chat.system.transform"',
            '"experimental.session.compacting"',
            '"tool.execute.after"',
            "vibe_workflow_status",
            "truncate(",
            "spawn(",
            "scheduleRefresh(",
        ):
            self.assertIn(required, text)
        for forbidden in (
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

    def test_plugin_loads_and_bridges_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.symlink(GLOBAL_NODE_MODULES, root / "node_modules")
            runtime = root / "runtime"
            (runtime / "scripts").mkdir(parents=True)
            stub = runtime / "scripts/vibe.py"
            stub.write_text(
                "import json, pathlib, sys\n"
                "log = pathlib.Path(__file__).resolve().parents[2] / 'invocations.jsonl'\n"
                "with log.open('a') as handle:\n"
                "    handle.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                "print(json.dumps({'current_task': {'id': 'TASK-001', 'status': 'in-progress'}}))\n",
                encoding="utf-8",
            )
            project = root / "project"
            (project / ".project-log").mkdir(parents=True)
            plugin = root / "vibe-workflow.ts"
            shutil.copy2(PLUGIN, plugin)
            log_path = root / "invocations.jsonl"
            probe = root / "probe.mjs"
            probe.write_text(
                Template(PROBE).substitute(
                    plugin_url=json.dumps(plugin.as_uri()),
                    project=json.dumps(str(project)),
                    log_path=json.dumps(str(log_path)),
                ),
                encoding="utf-8",
            )

            environment = os.environ.copy()
            environment.update({
                "VIBE_RUNTIME_SCRIPT": str(stub),
                "VIBE_PYTHON": "python3",
                "VIBE_REFRESH_DEBOUNCE_MS": "50",
                "OPENCODE_CONFIG_DIR": str(root / "config"),
            })
            result = subprocess.run(
                [str(NODE), "--no-warnings", str(probe)],
                env=environment, cwd=root, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(
                payload["hookNames"],
                [
                    "experimental.chat.system.transform",
                    "experimental.session.compacting",
                    "tool",
                    "tool.execute.after",
                ],
            )
            self.assertTrue(payload["systemInjected"])
            self.assertTrue(payload["compactionInjected"])
            self.assertIn("TASK-001", payload["statusOutput"])

            invocations = [
                json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()
            ]
            self.assertIn(["--root", str(project), "state-views"], invocations)
            self.assertIn(["--root", str(project), "status"], invocations)
            refreshes = [row for row in invocations if row[2:4] == ["evidence", "refresh"]]
            self.assertTrue(refreshes)
            self.assertTrue(all("--reason" in row for row in refreshes))
            self.assertTrue(any("src/app.py" in " ".join(row) for row in refreshes))
            self.assertTrue(any("bash" in " ".join(row) for row in refreshes))

    def test_plugin_degrades_safely_without_a_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            os.symlink(GLOBAL_NODE_MODULES, root / "node_modules")
            project = root / "project"
            (project / ".project-log").mkdir(parents=True)
            plugin = root / "vibe-workflow.ts"
            shutil.copy2(PLUGIN, plugin)
            probe = root / "probe.mjs"
            probe.write_text(
                "import { VibeWorkflowPlugin } from " + json.dumps(plugin.as_uri()) + "\n"
                "const hooks = await VibeWorkflowPlugin({ directory: " + json.dumps(str(project)) + ","
                " worktree: " + json.dumps(str(project)) + ","
                " client: { app: { log: async () => ({}) } } })\n"
                "const output = { system: [] }\n"
                'await hooks["experimental.chat.system.transform"]({ model: {} }, output)\n'
                "console.log('hooks=', Object.keys(hooks).sort().join(','))\n"
                "console.log('system=', JSON.stringify(output.system))\n",
                encoding="utf-8",
            )
            environment = os.environ.copy()
            for key in ("VIBE_RUNTIME_SCRIPT", "VIBE_RUNTIME", "VIBE_PYTHON"):
                environment.pop(key, None)
            environment.update({
                "HOME": str(root / "home"),
                "OPENCODE_CONFIG_DIR": str(root / "config"),
            })
            result = subprocess.run(
                [str(NODE), "--no-warnings", str(probe)],
                env=environment, cwd=root, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, check=False, timeout=90,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn("experimental.chat.system.transform", result.stdout)
            self.assertIn("No Vibe runtime was resolved", result.stdout)


if __name__ == "__main__":
    unittest.main()
