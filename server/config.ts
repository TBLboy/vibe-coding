import { resolve } from "node:path";

export interface TeamConfig { host: string; port: number; dbPath: string; tls?: { cert: string; key: string } }
export function readConfig(env: NodeJS.ProcessEnv = process.env): TeamConfig {
  const host = env.TEAM_HOST ?? "127.0.0.1", rawPort = env.TEAM_PORT ?? "7410";
  if (!host || /[\s\u0000-\u001f]/u.test(host)) throw new Error("Invalid TEAM_HOST");
  if (!/^(0|[1-9][0-9]*)$/u.test(rawPort) || Number(rawPort) > 65535) throw new Error("Invalid TEAM_PORT");
  const cert = env.TEAM_TLS_CERT, key = env.TEAM_TLS_KEY;
  // Both or neither: a half-configured listener would silently downgrade to plain HTTP.
  if ((cert === undefined) !== (key === undefined)) throw new Error("Invalid TEAM_TLS_CERT/TEAM_TLS_KEY: set both or neither");
  return { host, port: Number(rawPort), dbPath: resolve(env.TEAM_DB_PATH ?? "team-data/workspace.sqlite"),
    ...(cert && key ? { tls: { cert, key } } : {}) };
}
