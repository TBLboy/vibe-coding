import { resolve } from "node:path";
import { assertId } from "../runtime/core/team/binding.ts";

export interface TeamConfig { host:string; port:number; dbPath:string; orgId:string }
export function readConfig(env:NodeJS.ProcessEnv=process.env): TeamConfig {
  const host=env.TEAM_HOST??"127.0.0.1", rawPort=env.TEAM_PORT??"7410", orgId=env.TEAM_ORG_ID??"org_default";
  if(!host || /[\s\u0000-\u001f]/u.test(host)) throw new Error("Invalid TEAM_HOST");
  if(!/^(0|[1-9][0-9]*)$/u.test(rawPort) || Number(rawPort)>65535) throw new Error("Invalid TEAM_PORT");
  assertId(orgId,"workspaceId");
  return {host,port:Number(rawPort),orgId,dbPath:resolve(env.TEAM_DB_PATH??"team-data/workspace.sqlite")};
}
