import { mkdir, stat, chmod } from "node:fs/promises";
import { dirname } from "node:path";
import { pathToFileURL } from "node:url";
import type { AddressInfo } from "node:net";
import { readConfig } from "./config.ts";
import { openTeamDatabase } from "./store/sqlite.ts";
import { createAccount } from "./domain/identity.ts";
import { createTeamServer } from "./http/router.ts";

export async function main(): Promise<void> {
  const config=readConfig(), directory=dirname(config.dbPath);
  await mkdir(directory,{recursive:true,mode:0o700});
  if(process.platform!=="win32" && ((await stat(directory)).mode&0o077)!==0) throw new Error("Data directory must be owner-only");
  const store=openTeamDatabase(config.dbPath);
  try {
    await chmod(config.dbPath,0o600);
    if(process.argv[2]==="provision-account") {
      const {TEAM_ACCOUNT_EMAIL:email,TEAM_ACCOUNT_PASSWORD:password,TEAM_ACCOUNT_NAME:displayName}=process.env;
      if(!email || !password) throw new Error("Provisioning requires TEAM_ACCOUNT_EMAIL and TEAM_ACCOUNT_PASSWORD");
      const account=await createAccount(store,{orgId:config.orgId,email,password,displayName:displayName??email});
      process.stdout.write(JSON.stringify({event:"account_provisioned",accountId:account.id})+"\n"); store.close(); return;
    }
    if(process.argv[2]!==undefined) throw new Error("Unknown server command");
    const count=store.db.prepare("SELECT count(*) AS n FROM account WHERE org_id=?").get(config.orgId) as {n:number};
    if(count.n===0) {
      const {TEAM_BOOTSTRAP_EMAIL:email,TEAM_BOOTSTRAP_PASSWORD:password,TEAM_BOOTSTRAP_NAME:displayName}=process.env;
      if(!email || !password) throw new Error("First startup requires TEAM_BOOTSTRAP_EMAIL and TEAM_BOOTSTRAP_PASSWORD");
      await createAccount(store,{orgId:config.orgId,email,password,displayName:displayName??email});
    }
    const server=createTeamServer(store,{orgId:config.orgId,logger:entry=>process.stdout.write(JSON.stringify(entry)+"\n"),...(config.tls?{tls:config.tls}:{})});
    await new Promise<void>((resolve,reject)=>{server.once("error",reject);server.listen(config.port,config.host,resolve);});
    process.stdout.write(JSON.stringify({event:"listening",host:config.host,port:(server.address() as AddressInfo).port,tls:config.tls?"https":"http"})+"\n");
    let stopping=false;
    const stop=()=>{
      if(stopping)return; stopping=true;
      server.close(error=>{store.close();if(error)process.exitCode=1;});
    };
    process.once("SIGTERM",stop); process.once("SIGINT",stop);
  } catch(error) {store.close();throw error;}
}

if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  main().catch(error=>{
    // Validation messages are static; never print credentials, HTTP input or SQL values.
    process.stderr.write(error instanceof Error && /^(First startup|Provisioning requires|Data directory|Invalid TEAM_|Unknown server command)/u.test(error.message)
      ? `${error.message}\n` : "Team workspace server startup failed\n");
    process.exitCode=1;
  });
}
