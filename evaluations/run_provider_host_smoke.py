"""Opt-in live model smoke using the host's current authorized default route.

Never part of npm run verify. No new provider, global config edit or credentials in
argv/output. Resolved secret settings stay in memory/child environment; temporary
config, database and raw transcripts are removed on normal exit and SIGTERM/SIGINT.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import secrets
import signal
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROUTE_KEY_ENV = "VIBE_SMOKE_ROUTE_KEY"


class SmokeError(Exception):
    pass


class SmokeInterrupted(SmokeError):
    pass


class Termination:
    """Unwind blocking waits, not process acquisition or resource cleanup."""
    signum = None
    waiting = False

    def __enter__(self):
        self.previous = {sig: signal.signal(sig, self.interrupt) for sig in (signal.SIGTERM, signal.SIGINT)}
        return self

    def __exit__(self, *_):
        for sig, handler in self.previous.items():
            signal.signal(sig, handler)

    def interrupt(self, signum, _frame):
        if self.signum is None:
            self.signum = signum
            if self.waiting:
                raise SmokeInterrupted("smoke interrupted")

    @contextmanager
    def during_wait(self):
        try:
            self.waiting = True
            if self.signum is not None:
                raise SmokeInterrupted("smoke interrupted")
            yield
        finally:
            self.waiting = False

    def receive(self, messages, timeout):
        with self.during_wait():
            return messages.get(timeout=timeout)


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    for pipe in (process.stdout, process.stdin, process.stderr):
        if pipe:
            pipe.close()


def run_command(args, *, env, timeout, termination=None):
    process = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        with termination.during_wait() if termination else nullcontext():
            stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    finally:
        stop_process(process)


def api(method, path, body=None, *, env=None, server=None, timeout=180, termination=None):
    args = ["opencode", "api", method, path]
    if server:
        args += ["--server", server]
    if body is not None:
        args += ["--data", json.dumps(body)]
    result = run_command(args, env=env, timeout=timeout, termination=termination)
    if result.returncode:
        # CLI errors can contain provider settings; never echo stdout/stderr here.
        raise SmokeError("host API failed: " + method + " " + path.split("?")[0])
    if not result.stdout.strip():
        return None
    value = json.loads(result.stdout)
    return value.get("data", value) if isinstance(value, dict) else value


def private_json(path, value):
    with open(path, "w", opener=lambda p, f: os.open(p, f, 0o600)) as stream:
        json.dump(value, stream)


def isolated_env(caller, route_key, base):
    # Do not inherit provider, config, injection or trust-bypass variables by
    # name. Even an otherwise permitted variable must not contain the key.
    allowed = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "SSL_CERT_FILE", "SSL_CERT_DIR", "NODE_EXTRA_CA_CERTS")
    env = {name: caller[name] for name in allowed if name in caller and route_key not in caller[name]}
    home = base / "home"
    home.mkdir(mode=0o700)
    env.update(HOME=str(home), TMPDIR=str(base), OPENCODE_CONFIG_DIR=str(base / "profile"),
               OPENCODE_DB=str(base / "host.sqlite"))
    if any(route_key in value for value in env.values()):
        raise SmokeError("credential present in an isolated fixture path")
    return env


def route_config(model):
    """Stage only the observed built-in, API-key-backed Anthropic route shape."""
    if not isinstance(model, dict) or model.get("enabled") is not True:
        raise SmokeError("no enabled default model")
    package = "@opencode/ai/providers/anthropic"
    if model.get("package") != package:
        raise SmokeError("unsupported default provider package for this smoke")
    provider, model_id, upstream = (model.get(k) for k in ("providerID", "id", "modelID"))
    if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", v)
               for v in (provider, model_id, upstream)):
        raise SmokeError("unsupported default route identifiers")
    settings = model.get("settings")
    if not isinstance(settings, dict) or set(settings) - {"apiKey", "baseURL", "provider"}:
        raise SmokeError("unsupported default route settings")
    key, base_url = settings.get("apiKey"), settings.get("baseURL")
    if not isinstance(key, str) or not key.strip() or not isinstance(base_url, str):
        raise SmokeError("default route requires an API key and HTTPS endpoint")
    try:
        url = urlsplit(base_url)
        valid_url = (url.scheme == "https" and bool(url.hostname) and url.username is None
                     and url.password is None and not any(c in base_url for c in "?#\\")
                     and url.path in ("/v1", "/v1/") and not re.search(r"[\s\x00-\x1f\x7f]", base_url))
    except ValueError:
        valid_url = False
    if not valid_url:
        raise SmokeError("unsupported default route endpoint")
    staged = {"baseURL": base_url, "apiKey": "{env:" + ROUTE_KEY_ENV + "}"}
    if "provider" in settings:
        if settings["provider"] != provider:
            raise SmokeError("default route provider setting does not match its ID")
        staged["provider"] = provider

    caps, limit = model.get("capabilities"), model.get("limit")
    if (not isinstance(caps, dict) or caps.get("tools") is not True
            or not isinstance(limit, dict)):
        raise SmokeError("default route is missing tool capabilities or limits")
    for field, allowed in (("input", ("text", "image")), ("output", ("text",))):
        values = caps.get(field)
        if not isinstance(values, list) or "text" not in values or any(v not in allowed for v in values):
            raise SmokeError("unsupported default route modalities")
    limits = {k: limit[k] for k in ("context", "input", "output") if k in limit}
    if (not {"context", "output"} <= limits.keys()
            or any(type(v) is not int or v <= 0 for v in limits.values())):
        raise SmokeError("unsupported default route limits")
    config = {"$schema": "https://opencode.ai/config.json", "model": provider + "/" + model_id,
              "providers": {provider: {"package": package, "settings": staged,
                  "models": {model_id: {"modelID": upstream, "name": model_id,
                      "capabilities": {k: caps[k] for k in ("tools", "input", "output")}, "limit": limits}}}}}
    if key in json.dumps(config, ensure_ascii=False):
        raise SmokeError("route configuration contains credential outside its substitution")
    return config, key


def channel(process, predicate):
    """Bounded stdout readiness, not a polling loop. Never forward raw output."""
    messages = queue.Queue()

    def consume():
        for line in process.stdout:
            if predicate(line):
                messages.put(line)
    threading.Thread(target=consume, daemon=True).start()
    return messages


def native_tools(context):
    return [part for message in context if message.get("type") == "assistant"
            for part in message.get("content", []) if part.get("type") == "tool"]


def tools(context):
    """Retain native Code Mode provenance: child status is host-owned metadata;
    the associated result is the completed execute wrapper's real output.
    """
    calls=[]
    for part in native_tools(context):
        nested=part.get("state",{}).get("metadata",{}).get("toolCalls",[])
        if part.get("name")=="execute" and nested:
            for child in nested:
                calls.append({"name":child.get("tool"),"state":{
                    "status":child.get("status") if part["state"]["status"]=="completed" else "error",
                    "input":child.get("input",{}),"content":part["state"].get("content",[])}})
        else:
            calls.append(part)
    return calls


def output(tool):
    return "\n".join(c.get("text", "") for c in tool.get("state", {}).get("content", []) if isinstance(c, dict))


def successful(context):
    idle = [m for m in context if m.get("type") == "idle"]
    return bool(idle and idle[-1].get("outcome") == "succeeded")


# Test-only observer runs after the unmodified staged plugin and stores only
# whitelisted flags/status, never raw system prompts or tool results.
OBSERVER_SOURCE = '''import { Plugin } from "@opencode/plugin";
import { appendFile } from "node:fs/promises";
export default Plugin.define({id:"vibe-smoke-observer",async setup(ctx){
 const save=value=>appendFile(process.env.VIBE_SMOKE_OBSERVATIONS,JSON.stringify(value)+"\\n",{mode:0o600});
 await ctx.session.hook("context",async e=>{
  const text=e.system.map(p=>p.type==="text"?p.text:"").join("\\n");
  await save({kind:"context",sessionID:e.sessionID,
   mode:text.match(/Authoritative Session mode: (fast|balanced|strict)/)?.[1]??null,
   team:text.includes("[Team workspace —"),tools:Object.keys(e.tools)});
 });
 const syncStatus=value=>{
  if(typeof value==="string"){try{return syncStatus(JSON.parse(value));}catch{return null;}}
  if(!value||typeof value!=="object")return null;
  if(value.status==="synced"||value.status==="saved_locally")return value.status;
  for(const v of Object.values(value)){const found=syncStatus(v);if(found)return found;}
  return null;
 };
 const statusOK=result=>{
  const content=result?.content??result?.output;
  const text=Array.isArray(content)&&content.length===1&&content[0]?.type==="text"?content[0].text:content;
  if(typeof text!=="string")return false;
  try{
   const value=JSON.parse(text);
   return value?.ok===true&&value.lastError===null&&!Object.hasOwn(value,"error");
  }catch{return false;}
 };
 await ctx.tool.hook("execute.after",async e=>{
  const record={kind:"tool",sessionID:e.sessionID,tool:e.tool,status:e.status};
  if(e.tool==="workspace_record_progress")await save({...record,syncStatus:syncStatus(e.result)});
  if(e.tool==="workspace_status")await save({...record,ok:e.status==="completed"&&statusOK(e.result)});
 });
 }});
'''


def check_workspace_status(observed, session_id, expected_calls):
    results = [{"status": x["status"], "ok": x["ok"]} for x in observed
               if x.get("kind") == "tool" and x.get("sessionID") == session_id and x.get("tool") == "workspace_status"]
    if not results or len(results) != expected_calls or any(
            x["status"] != "completed" or x["ok"] is not True for x in results):
        raise SmokeError("actual workspace status result was not successful")
    return results


def main():
    with Termination() as termination:
        return run_smoke(termination)


def run_smoke(termination):
    summary = {"scope": "real provider command and bound team tools", "passed": False}
    processes = []
    route_key = None
    parent = Path(os.environ.get("TMPDIR", tempfile.gettempdir())).resolve()
    with tempfile.TemporaryDirectory(prefix="vibe-provider-smoke-", dir=parent) as directory:
        base = Path(directory)
        profile, project = base / "profile", base / "project"
        profile.mkdir(mode=0o700); project.mkdir(mode=0o700)
        try:
            model = api("get", "/api/model/default", termination=termination)
            config, route_key = route_config(model)
            provider_id, model_id = config["model"].split("/", 1)
            summary["model"] = {"providerID": provider_id, "id": model_id, "package": config["providers"][provider_id]["package"]}
            env = isolated_env(os.environ, route_key, base)
            private_json(profile / "opencode.json", config)
            install = run_command(["python3", str(ROOT / "scripts/vibe_v2_installer.py"), "install", "--opencode-home", str(profile)],
                                  env=env, timeout=30, termination=termination)
            if install.returncode:
                raise SmokeError("isolated installation failed")
            (project / ".vibe").mkdir(mode=0o700)
            (project / "AGENTS.md").write_text("# Host acceptance fixture\nOnly perform the explicit smoke request. Do not read configuration, credentials or unrelated files; do not invoke subagents.\n")

            observer = profile / "observer"; observer.mkdir()
            (observer / "index.ts").write_text(OBSERVER_SOURCE)
            installed = json.loads((profile / "opencode.json").read_text())
            installed["plugin"].append(str(observer))
            private_json(profile / "opencode.json", installed)
            observations = base / "observations.jsonl"
            client_env = {**env, "OPENCODE_PASSWORD": secrets.token_urlsafe(32)}
            host_env = {**client_env, ROUTE_KEY_ENV: route_key, "VIBE_SMOKE_OBSERVATIONS": str(observations)}
            with open(base / "host.stderr", "w", opener=lambda p,f: os.open(p,f,0o600)) as stderr:
                host = subprocess.Popen(["opencode", "serve", "--hostname", "127.0.0.1", "--port", "0"], cwd=project,
                                        env=host_env, stdout=subprocess.PIPE, stderr=stderr, text=True)
                processes.append(host)
                ready = termination.receive(channel(host, lambda line: "server listening on " in line), timeout=20)
                server = re.search(r"http://127\.0\.0\.1:\d+", ready).group(0)
                call = lambda method, path, body=None: api(method, path, body, env=client_env, server=server, termination=termination)
                summary["hostVersion"] = call("get", "/api/info")["version"]
                session = call("post", "/api/session", {"agent": "vibe-main", "location": {"directory": str(project)}, "title": "Unbound native mode smoke"})
                sid = session["id"]
                if not (base / "host.sqlite").is_file():
                    raise SmokeError("isolated host database not created")
                summary["isolatedDatabase"] = True
                call("post", f"/api/session/{sid}/command", {"name": "fast", "text": ""})
                call("post", f"/api/experimental/session/{sid}/wait")
                context = call("get", f"/api/session/{sid}/context")
                if not successful(context):
                    raise SmokeError("unbound model command did not succeed")
                command_tools = tools(context)
                summary["nativeCommandTrace"] = [{"name":x.get("name"),"status":x.get("state",{}).get("status")} for x in command_tools]
                if not any(x["name"] == "vibe_set_session_mode" and x["state"]["status"] == "completed" and
                           x["state"].get("input",{}).get("mode")=="fast" and "changed to fast" in output(x) for x in command_tools):
                    raise SmokeError("native command lacks successful mode-tool trace")
                if any(x["name"]!="vibe_set_session_mode" for x in command_tools):
                    raise SmokeError("bare mode command performed extra work")
                summary["nativeFastCommand"] = {"outcome": "succeeded", "modeToolCompleted": True}

                spec_marker, progress_marker = "SPEC_" + secrets.token_hex(8), "PROGRESS_" + secrets.token_hex(8)
                fixture = subprocess.Popen(["node", "--experimental-strip-types", str(ROOT / "evaluations/provider_host_fixture.ts"), str(project), str(profile), spec_marker, progress_marker], env=env,
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
                processes.append(fixture)
                fixture_messages = channel(fixture, lambda line: line.startswith("{"))
                fixture_info = json.loads(termination.receive(fixture_messages, timeout=20))
                if not fixture_info.get("ready"):
                    raise SmokeError("workbench fixture not ready")
                call("post", "/api/location/reload")
                bound = call("post", "/api/session", {"agent": "vibe-main", "location": {"directory": str(project)}, "title": "Bound team tool smoke"})
                bid = bound["id"]
                prompt = ("This is a bounded one-turn fixture check, not implementation. First use workspace_query_spec for specs/host-smoke.md; "
                          "then workspace_record_progress kind=progress mode=append text=" + progress_marker + "; then workspace_status. "
                          "Do not use shell, other file tools, Skills or subagents. Reply with the spec verification marker and confirmation only after successful tool results.")
                call("post", f"/api/session/{bid}/command", {"name": "balanced", "text": prompt})
                call("post", f"/api/experimental/session/{bid}/wait")
                bound_context = call("get", f"/api/session/{bid}/context")
                if not successful(bound_context):
                    raise SmokeError("bound model workflow did not succeed")
                bound_tools = tools(bound_context)
                completed = [x for x in bound_tools if x["state"]["status"] == "completed"]
                names = [x["name"] for x in completed]
                for name in ["vibe_set_session_mode", "workspace_query_spec", "workspace_record_progress", "workspace_status"]:
                    if name not in names:
                        raise SmokeError("required model-driven tool missing: " + name)
                if any(x["state"]["status"]!="completed" for x in bound_tools) or any(name not in
                    ["vibe_set_session_mode","workspace_query_spec","workspace_record_progress","workspace_status"] for name in names):
                    raise SmokeError("bound workflow invoked an unexpected or incomplete tool")
                if not any(x["name"]=="vibe_set_session_mode" and x["state"].get("input",{}).get("mode")=="balanced"
                           and "changed to balanced" in output(x) for x in completed):
                    raise SmokeError("balanced command lacks successful mode transition")
                if not any(x["name"] == "workspace_query_spec" and spec_marker in output(x) for x in completed):
                    raise SmokeError("spec challenge absent from real tool result")
                observed = [json.loads(line) for line in observations.read_text().splitlines()]
                progress_observed=[x for x in observed if x.get("kind")=="tool" and x["sessionID"]==bid and x.get("tool")=="workspace_record_progress"]
                summary["actualProgressToolResults"]=[{"status":x["status"],"syncStatus":x["syncStatus"]} for x in progress_observed]
                if not any(x["status"]=="completed" and x["syncStatus"]=="synced" for x in progress_observed):
                    raise SmokeError("actual progress tool result was not synced")
                summary["actualWorkspaceStatusResults"] = check_workspace_status(observed, bid, names.count("workspace_status"))
                texts = [p.get("text", "") for m in bound_context if m.get("type") == "assistant" for p in m.get("content", []) if p.get("type") == "text"]
                if not any(spec_marker in text for text in texts):
                    raise SmokeError("model reply did not use hidden spec challenge")
                fixture.stdin.write("check\n"); fixture.stdin.flush()
                oracle = json.loads(termination.receive(fixture_messages, timeout=10))
                local = project / ".vibe/members" / oracle["accountId"] / "progress.md"
                if not oracle["progressMatch"] or oracle["version"] != 1 or hashlib.sha256(local.read_bytes()).hexdigest() != oracle["hash"]:
                    raise SmokeError("independent server/file oracle mismatch")
                if not any(x.get("kind")=="context" and x["sessionID"] == sid and x["mode"] == "fast" and not x["team"] for x in observed):
                    raise SmokeError("unbound authoritative fast context not observed")
                if not any(x.get("kind")=="context" and x["sessionID"] == bid and x["mode"] == "balanced" and x["team"] for x in observed):
                    raise SmokeError("bound authoritative balanced/team context not observed")
                summary["boundWorkflow"] = {"outcome": "succeeded", "completedTools": names, "specChallenge": True,
                                             "serverProgressVersion": oracle["version"], "serverFileHashMatch": True}
                summary["contextObserver"] = {"unboundFast": True, "boundBalancedTeam": True}
                summary["passed"] = True
        except Exception as error:
            summary["error"] = str(error) if isinstance(error, SmokeError) else type(error).__name__
            frames=[]; trace=error.__traceback__
            while trace:
                frames.append({"file":Path(trace.tb_frame.f_code.co_filename).name,"line":trace.tb_lineno})
                trace=trace.tb_next
            summary["failureFrames"] = frames
        finally:
            for process in reversed(processes):
                stop_process(process)
            # No raw provider settings/transcripts survive the temporary directory.
    summary["temporaryArtifactsRemoved"] = not base.exists()
    if termination.signum is not None:
        summary.update(passed=False, error="smoke interrupted", signal=signal.Signals(termination.signum).name)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if route_key and route_key in rendered:
        print('{"passed":false,"error":"output secret guard"}')
        return 1
    print(rendered)
    if termination.signum is not None:
        return 128 + termination.signum
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
