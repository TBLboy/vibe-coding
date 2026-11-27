import { mkdir, stat, chmod } from "node:fs/promises";
import { dirname } from "node:path";
import { pathToFileURL } from "node:url";
import type { AddressInfo } from "node:net";
import { readConfig } from "./config.ts";
import { readAdminToken } from "./domain/admin.ts";
import { openTeamDatabase } from "./store/sqlite.ts";
import { createTeamServer } from "./http/router.ts";

export async function main(): Promise<void> {
  const config = readConfig(), adminToken = readAdminToken(), directory = dirname(config.dbPath);
  await mkdir(directory, { recursive: true, mode: 0o700 });
  if (process.platform !== "win32" && ((await stat(directory)).mode & 0o077) !== 0) throw new Error("Data directory must be owner-only");
  const store = openTeamDatabase(config.dbPath);
  try {
    await chmod(config.dbPath, 0o600);
    if (process.argv[2] !== undefined) throw new Error("Unknown server command");
    const server = createTeamServer(store, { adminToken, logger: (entry) => process.stdout.write(JSON.stringify(entry) + "\n"), ...(config.tls ? { tls: config.tls } : {}) });
    await new Promise<void>((resolve, reject) => { server.once("error", reject); server.listen(config.port, config.host, resolve); });
    // Env switches must be visible at startup: WORKBENCH_ADMIN_TOKEN is required (value never printed).
    process.stdout.write(JSON.stringify({ event: "listening", host: config.host, port: (server.address() as AddressInfo).port, tls: config.tls ? "https" : "http", adminToken: "configured" }) + "\n");
    let stopping = false;
    const stop = () => {
      if (stopping) return; stopping = true;
      server.close((error) => { store.close(); if (error) process.exitCode = 1; });
    };
    process.once("SIGTERM", stop); process.once("SIGINT", stop);
  } catch (error) { store.close(); throw error; }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    // Validation messages are static; never print credentials, HTTP input or SQL values.
    process.stderr.write(error instanceof Error && /^(WORKBENCH_ADMIN_TOKEN|Data directory|Invalid TEAM_|Unknown server command)/u.test(error.message)
      ? `${error.message}\n` : "Workbench server startup failed\n");
    process.exitCode = 1;
  });
}
