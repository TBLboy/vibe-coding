"""Local harness regressions, not a substitute for live provider execution."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from evaluations.run_provider_host_smoke import (
    OBSERVER_SOURCE, ROOT, ROUTE_KEY_ENV, SmokeError, api, check_workspace_status,
    native_tools, output, private_json, route_config, tools,
)


class HostSmokeHarnessTests(unittest.TestCase):
    def route(self):
        return {"enabled": True, "id": "fixture-model", "modelID": "fixture-upstream",
                "providerID": "fixture-provider", "package": "@opencode/ai/providers/anthropic",
                "settings": {"apiKey": "fixture-key-never-print", "baseURL": "https://example.test/v1",
                             "provider": "fixture-provider"},
                "capabilities": {"tools": True, "input": ["text", "image"], "output": ["text"]},
                "limit": {"context": 500000, "output": 32000}}

    def test_resolved_route_config_keeps_key_separate_and_ignores_extra_metadata(self):
        model = self.route()
        model["metadata"] = {"private": "unexpected-metadata"}
        model["capabilities"]["private"] = "unexpected-capability"
        config, key = route_config(model)
        self.assertEqual(key, model["settings"]["apiKey"])
        provider = config["providers"]["fixture-provider"]
        self.assertEqual(config["model"], "fixture-provider/fixture-model")
        self.assertEqual(provider["settings"], {"baseURL": "https://example.test/v1", "provider": "fixture-provider",
                                                "apiKey": "{env:VIBE_SMOKE_ROUTE_KEY}"})
        self.assertEqual(provider["models"]["fixture-model"]["modelID"], "fixture-upstream")
        self.assertEqual(provider["models"]["fixture-model"]["capabilities"], {"tools": True, "input": ["text", "image"], "output": ["text"]})
        serialized = json.dumps(config)
        for value in (key, "unexpected-metadata", "unexpected-capability"):
            self.assertNotIn(value, serialized)

    def test_unhandled_route_settings_and_credential_bearing_url_fail_closed(self):
        secret = "fixture-key-never-print"
        for change in ({"headers": {"X-Auth": secret}}, {"baseURL": f"https://example.test/v1?key={secret}"},
                       {"baseURL": f"https://{secret}@example.test/v1"}, {"baseURL": f"https://example.test/{secret}"},
                       {"baseURL": "http://example.test/v1"}, {"apiKey": ""}):
            with self.subTest(case=next(iter(change))):
                model = self.route()
                model["settings"].update(change)
                with self.assertRaises(SmokeError) as raised:
                    route_config(model)
                self.assertNotIn(secret, str(raised.exception))

    def test_unhandled_provider_package_is_not_staged(self):
        model = self.route()
        model["package"] = "file:///not-a-builtin-provider"
        with self.assertRaises(SmokeError):
            route_config(model)

    def test_key_in_an_otherwise_valid_model_id_is_not_staged(self):
        model = self.route()
        key = model["settings"]["apiKey"]
        model["modelID"] = key
        with self.assertRaises(SmokeError) as raised:
            route_config(model)
        self.assertNotIn(key, str(raised.exception))

    def test_code_mode_trace_requires_completed_parent_and_child(self):
        part={"type":"tool","name":"execute","state":{"status":"completed",
              "content":[{"type":"text","text":"Session mode changed to fast."}],
              "metadata":{"toolCalls":[{"tool":"vibe_set_session_mode","status":"completed","input":{"mode":"fast"}}]}}}
        context=[{"type":"assistant","content":[part]}]
        self.assertEqual(native_tools(context)[0]["name"],"execute")
        normalized=tools(context)[0]
        self.assertEqual(normalized["name"],"vibe_set_session_mode")
        self.assertEqual(normalized["state"]["input"]["mode"],"fast")
        self.assertEqual(output(normalized),"Session mode changed to fast.")
        part["state"]["status"]="error"
        self.assertEqual(tools(context)[0]["state"]["status"],"error")
        part["state"]["status"]="completed"
        part["state"]["metadata"]["toolCalls"][0]["status"]="error"
        self.assertEqual(tools(context)[0]["state"]["status"],"error")

    def test_host_api_error_does_not_echo_response_or_credential(self):
        secret="fixture-secret-never-print"
        with patch("evaluations.run_provider_host_smoke.run_command",
                   return_value=SimpleNamespace(returncode=1,stdout=secret,stderr=secret)):
            with self.assertRaises(Exception) as raised:
                api("get","/api/model/default")
        self.assertNotIn(secret,str(raised.exception))

    def test_workspace_status_accepts_only_actual_successful_hook_payloads(self):
        with tempfile.TemporaryDirectory() as directory:
            observations = Path(directory) / "status.jsonl"
            # Run the actual observer callback with a stub hook registration.
            script = OBSERVER_SOURCE.replace('import { Plugin } from "@opencode/plugin";',
                                             'const Plugin = {define: value => value};')
            script = script.replace("export default Plugin.define", "const observer = Plugin.define")
            script += '''
let after;
await observer.setup({session:{hook(){}},tool:{hook(_name, cb){after=cb;}}});
const payloads = [
 {content:[{type:"text",text:'{"ok":true,"lastError":null}'}]},
 {content:[{type:"text",text:'{"error":"fixture-error-do-not-record"}'}]},
 {content:'{"ok":false,"lastError":"fixture-error-do-not-record"}'},
 {content:'{"ok":true,"lastError":null,"error":"fixture-error-do-not-record"}'},
 {content:'{"ok":true,"lastError":"fixture-error-do-not-record"}'},
 {content:'not JSON'},
];
for (const [i,result] of payloads.entries())
 await after({sessionID:String(i),tool:"workspace_status",status:"completed",result});
await after({sessionID:"failed",tool:"workspace_status",status:"error",result:payloads[0]});
'''
            subprocess.run(["node", "--input-type=module", "-e", script], check=True, timeout=10,
                           env={"PATH": os.environ["PATH"], "VIBE_SMOKE_OBSERVATIONS": str(observations)})
            raw = observations.read_text()
            self.assertNotIn("fixture-error-do-not-record", raw)
            records = [json.loads(line) for line in raw.splitlines()]
            self.assertEqual(check_workspace_status(records, "0", 1), [{"status": "completed", "ok": True}])
            for session in ("1", "2", "3", "4", "5", "failed", "absent"):
                with self.subTest(session=session), self.assertRaises(SmokeError):
                    check_workspace_status(records, session, 1)
            with self.assertRaises(SmokeError):
                check_workspace_status(records, "0", 2)

    @unittest.skipUnless(os.name == "posix", "requires POSIX subprocess signals")
    def test_real_child_boundaries_and_sigterm_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            route = self.route()
            key = route["settings"].pop("apiKey")
            # Fake executables only: all process launches, waits and cleanup are
            # the real harness, but neither OpenCode nor a provider is contacted.
            script = f"#!{sys.executable}\n" + f"ROOT = {str(base)!r}\nROUTE = {route!r}\n" + '''
import json, os, signal, sys
from pathlib import Path
root = Path(ROOT)
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
key = "fixture-key-never-print"

def record(role):
    report = {"pid":os.getpid(),"keyVars":sorted(k for k,v in os.environ.items() if key in v),
              "isolatedHome":str(root) in os.environ.get("HOME", "")}
    p = root / (role + ".tmp")
    p.write_text(json.dumps(report))
    p.rename(root / (role + ".json"))

if tool == "python3":
    record("installer")
    path = Path(args[-1]) / "opencode.json"
    value = json.loads(path.read_text())
    assert key not in path.read_text()
    value["plugin"] = []
    path.write_text(json.dumps(value))
elif tool == "node":
    record("fixture")
    Path(os.environ["TMPDIR"], "team.sqlite").touch()
    print('{"ready":true}', flush=True)
    signal.pause()
elif args[0] == "serve":
    record("host")
    Path(os.environ["OPENCODE_DB"]).touch()
    print("server listening on http://127.0.0.1:12345", flush=True)
    signal.pause()
elif args[2] == "/api/model/default":
    record("discovery")
    ROUTE["settings"]["apiKey"] = os.environ["UNRELATED_ROUTE_ALIAS"]
    print(json.dumps(ROUTE))
elif args[2] == "/api/info":
    record("client")
    print('{"version":"synthetic"}')
elif args[2] == "/api/session":
    print('{"id":"fixture-session"}')
elif args[2].endswith("/context"):
    print(json.dumps([{"type":"idle","outcome":"succeeded"}, {"type":"assistant","content":[
      {"type":"tool","name":"vibe_set_session_mode","state":{"status":"completed","input":{"mode":"fast"},
        "content":[{"type":"text","text":"changed to fast"}]}}]}]))
elif args[2].endswith("/wait") and (root / "fixture.json").exists():
    record("waiting-client")
    signal.pause()
'''
            for executable in ("opencode", "python3", "node"):
                path = base / executable
                path.write_text(script)
                path.chmod(0o700)
            env = {"PATH": str(base), "TMPDIR": str(base), "HOME": os.environ["HOME"],
                   "UNRELATED_ROUTE_ALIAS": key, "ANOTHER_EXPORT": key,
                   ROUTE_KEY_ENV: "old-should-not-be-forwarded", "LANG": "prefix-" + key}
            waiting = base / "waiting-client.json"
            with subprocess.Popen([sys.executable, str(ROOT / "evaluations/run_provider_host_smoke.py")],
                                  env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as smoke:
                try:
                    deadline = time.monotonic() + 10
                    while not waiting.exists() and smoke.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(waiting.exists(), "synthetic model wait was not reached")
                    roots = list(base.glob("vibe-provider-smoke-*"))
                    self.assertEqual(len(roots), 1)
                    self.assertTrue((roots[0] / "host.sqlite").exists())
                    self.assertTrue((roots[0] / "team.sqlite").exists())
                    smoke.send_signal(signal.SIGTERM)
                    stdout, stderr = smoke.communicate(timeout=10)
                finally:
                    if smoke.poll() is None:
                        smoke.kill()
                    for name in ("host", "fixture", "waiting-client"):
                        record = base / f"{name}.json"
                        if record.exists() and smoke.returncode != 128 + signal.SIGTERM:
                            try:
                                os.kill(json.loads(record.read_text())["pid"], signal.SIGKILL)
                            except ProcessLookupError:
                                pass
            self.assertEqual(smoke.returncode, 128 + signal.SIGTERM)
            summary = json.loads(stdout)
            self.assertIs(summary["passed"], False)
            self.assertEqual(summary["signal"], "SIGTERM")
            self.assertIs(summary["temporaryArtifactsRemoved"], True)
            self.assertFalse(roots[0].exists())
            self.assertNotIn(key, stdout + stderr)
            for name, expected in (("discovery", ["ANOTHER_EXPORT", "LANG", "UNRELATED_ROUTE_ALIAS"]),
                                   ("host", [ROUTE_KEY_ENV]), ("installer", []), ("client", []),
                                   ("fixture", []), ("waiting-client", [])):
                with self.subTest(role=name):
                    report = json.loads((base / f"{name}.json").read_text())
                    self.assertEqual(report["keyVars"], expected)
                    self.assertEqual(report["isolatedHome"], name != "discovery")
                    if name in ("host", "fixture", "waiting-client"):
                        with self.assertRaises(ProcessLookupError):
                            os.kill(report["pid"], 0)

    def test_private_config_write_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"config.json"
            private_json(path,{"apiKey":"{env:TEST_SECRET}"})
            self.assertEqual(json.loads(path.read_text()),{"apiKey":"{env:TEST_SECRET}"})
            if os.name!="nt":self.assertEqual(path.stat().st_mode&0o777,0o600)


if __name__=="__main__":unittest.main()
