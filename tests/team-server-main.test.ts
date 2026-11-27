import assert from "node:assert/strict";
import test from "node:test";
import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { once } from "node:events";
import { readConfig } from "../server/config.ts";

const ADMIN = "a".repeat(40);

test("server configuration defaults to loopback and validates ports and TLS", () => {
  assert.equal(readConfig({}).host, "127.0.0.1");
  assert.equal(readConfig({ TEAM_PORT: "0" }).port, 0);
  for (const port of ["-1", "65536", "abc", "1.5"]) assert.throws(() => readConfig({ TEAM_PORT: port }), /TEAM_PORT/);
  assert.equal(readConfig({}).tls, undefined);
  assert.deepEqual(readConfig({ TEAM_TLS_CERT: "/c.pem", TEAM_TLS_KEY: "/k.pem" }).tls, { cert: "/c.pem", key: "/k.pem" });
  assert.throws(() => readConfig({ TEAM_TLS_CERT: "/c.pem" }), /TEAM_TLS_CERT/);
});

async function start(env: Record<string, string>) {
  const child = spawn(process.execPath, ["--experimental-strip-types", resolve("server/main.ts")], { env: { ...process.env, ...env }, stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  let output = "", errors = "";
  child.stderr.on("data", (c) => { errors += c.toString(); });
  const exited = once(child, "exit");
  const port = await new Promise<number>((res, rej) => {
    child.stdout.on("data", (c) => {
      output += c.toString();
      for (const line of output.split("\n")) { try { const e = JSON.parse(line); if (e.event === "listening") res(e.port); } catch { /* partial line */ } }
    });
    child.once("error", rej); child.once("exit", (code) => rej(new Error(`Server exited ${code}: ${errors}`)));
  });
  return { child, port, exited, output: () => output };
}

test("server refuses to start without a strong admin token", { timeout: 30000 }, async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "wb-noadmin-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const child = spawn(process.execPath, ["--experimental-strip-types", resolve("server/main.ts")], { env: { ...process.env, TEAM_DB_PATH: join(dir, "w.sqlite"), TEAM_PORT: "0", WORKBENCH_ADMIN_TOKEN: "short" }, stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  let err = ""; child.stderr.on("data", (c) => { err += c.toString(); });
  const [code] = await once(child, "exit");
  assert.equal(code, 1);
  assert.match(err, /WORKBENCH_ADMIN_TOKEN/);
});

test("production entrypoint serves the API and never prints the admin token", { timeout: 30000 }, async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "wb-main-"));
  const s = await start({ TEAM_DB_PATH: join(dir, "w.sqlite"), TEAM_PORT: "0", TEAM_HOST: "127.0.0.1", WORKBENCH_ADMIN_TOKEN: ADMIN });
  t.after(async () => { if (s.child.exitCode === null && s.child.signalCode === null) { s.child.kill(); await s.exited; } await rm(dir, { recursive: true, force: true }); });
  const base = `http://127.0.0.1:${s.port}`;
  assert.equal((await fetch(base + "/api/healthz")).status, 200);
  assert.equal((await fetch(base + "/api/workspaces")).status, 401);
  const created = await fetch(base + "/api/workspaces", { method: "POST", headers: { authorization: `Bearer ${ADMIN}`, "content-type": "application/json" }, body: JSON.stringify({ name: "E2E" }) });
  assert.equal(created.status, 201);
  const body = await created.json() as { key: string; workspace: { type: string } };
  assert.equal(body.workspace.type, "engineering-dev");
  const connect = await fetch(base + "/api/connect", { method: "POST", headers: { authorization: `Bearer ${body.key}` } });
  assert.equal(connect.status, 200);
  assert.equal(s.output().includes(ADMIN), false);
  assert.equal(s.output().includes(body.key), false);
});
