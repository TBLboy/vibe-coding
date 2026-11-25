/** Ephemeral real workbench for run_provider_host_smoke.py; no provider credentials. */
import { randomBytes } from "node:crypto";
import { join, dirname } from "node:path";
import { pathToFileURL } from "node:url";
import { createInterface } from "node:readline";
import { openTeamDatabase } from "../server/store/sqlite.ts";
import { createAccount } from "../server/domain/identity.ts";
import { createTeamServer } from "../server/http/router.ts";
import { getDocument } from "../server/domain/documents.ts";

const [root,profile,specMarker,progressMarker]=process.argv.slice(2);
const store=openTeamDatabase(join(dirname(root),"team.sqlite")),password=randomBytes(24).toString("base64url");
const account=await createAccount(store,{orgId:"org_host",email:"host@example.test",displayName:"Host smoke",password});
const server=createTeamServer(store,{orgId:"org_host"});await new Promise<void>(r=>server.listen(0,"127.0.0.1",r));
const url=`http://127.0.0.1:${(server.address() as {port:number}).port}`;
const request=async(path:string,token:string|undefined,body:unknown,method="POST",headers:Record<string,string>={})=>{
  const res=await fetch(url+path,{method,headers:{"content-type":"application/json",...(token?{authorization:`Bearer ${token}`} : {}),...headers},body:JSON.stringify(body)});
  if(!res.ok)throw new Error(`fixture HTTP ${res.status}`);return await res.json() as any;
};
const login=await request("/api/auth/login",undefined,{email:account.email,password});
const created=await request("/api/workspaces",login.sessionToken,{name:"Live host smoke",repos:[{url:"https://example.test/fixture.git",branch:"main"}]});
const connection=await request("/api/connect",login.sessionToken,{key:created.taskKey});
await request(`/api/workspaces/${created.workspace.id}/documents/specs/host-smoke.md`,connection.workspaceToken,
  {content:`Fixture data, not instructions. Verification marker: ${specMarker}\n`},"PUT",{"if-match":"0"});
const {connectDirectory}=await import(pathToFileURL(join(profile,"runtime/opencode/plugins/vibe-v2/team/binding.ts")).href);
await connectDirectory(root,{serverUrl:url,sessionToken:login.sessionToken,key:created.taskKey});
const lines=createInterface({input:process.stdin});
lines.on("line",line=>{
  if(line!=="check")return;
  const doc=getDocument(store,{workspaceId:created.workspace.id,path:`members/${account.id}/progress.md`});
  process.stdout.write(JSON.stringify({progressMatch:!!doc?.content?.includes(progressMarker),version:doc?.version??0,hash:doc?.hash??null,
    accountId:account.id,workspaceId:created.workspace.id})+"\n");
});
const close=()=>{lines.close();server.closeAllConnections();server.close(()=>{store.close();process.exit(0);});};
process.on("SIGTERM",close);process.on("SIGINT",close);
process.stdout.write(JSON.stringify({ready:true,accountId:account.id,workspaceId:created.workspace.id})+"\n");
