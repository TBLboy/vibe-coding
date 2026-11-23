import assert from "node:assert/strict";
import test from "node:test";
import { spawn } from "node:child_process";
import { mkdtemp, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { once } from "node:events";
import { readConfig } from "../server/config.ts";
import { openTeamDatabase } from "../server/store/sqlite.ts";

test("server configuration defaults to loopback and validates ports", () => {
  assert.equal(readConfig({}).host,"127.0.0.1");
  assert.equal(readConfig({TEAM_PORT:"0"}).port,0);
  for(const port of ["-1","65536","abc","1.5"]) assert.throws(()=>readConfig({TEAM_PORT:port}),/TEAM_PORT/);
  assert.throws(()=>readConfig({TEAM_ORG_ID:"../bad"}),/workspaceId/);
});

test("production entrypoint bootstraps explicitly, serves HTTP and shuts down with persistent hashes", {timeout:30000}, async t => {
  const dir=await mkdtemp(join(tmpdir(),"team-main-")), dbPath=join(dir,"workspace.sqlite"), password="temporary test bootstrap 123";
  const env={...process.env,TEAM_DB_PATH:dbPath,TEAM_PORT:"0",TEAM_HOST:"127.0.0.1",TEAM_ORG_ID:"org_main_test",TEAM_BOOTSTRAP_EMAIL:"boot@example.test",TEAM_BOOTSTRAP_PASSWORD:password};
  const child=spawn(process.execPath,["--experimental-strip-types",resolve("server/main.ts")],{env,stdio:["ignore","pipe","pipe"],windowsHide:true});
  let output="", errors=""; child.stderr.on("data",chunk=>{errors+=chunk.toString();});
  const exit=once(child,"exit");
  t.after(async()=>{if(child.exitCode===null && child.signalCode===null){child.kill("SIGTERM");await exit;} await rm(dir,{recursive:true,force:true});});
  const listening=new Promise<number>((resolvePort,reject)=>{
    child.stdout.on("data",chunk=>{
      output+=chunk.toString();
      for(const line of output.split("\n")) {
        try {const entry=JSON.parse(line);if(entry.event==="listening")resolvePort(entry.port);}catch{}
      }
    });
    child.once("error",reject); child.once("exit",code=>reject(new Error(`Server exited ${code}: ${errors}`)));
  });
  const port=await listening, base=`http://127.0.0.1:${port}`;
  assert.equal((await fetch(base+"/api/healthz")).status,200);
  const response=await fetch(base+"/api/auth/login",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({email:"boot@example.test",password})});
  assert.equal(response.status,200); const login=await response.json() as any;
  assert.ok(login.sessionToken); assert.equal(output.includes(password),false); assert.equal(output.includes(login.sessionToken),false);
  child.kill("SIGTERM"); const [code]=await exit; assert.equal(code,0,errors);
  const store=openTeamDatabase(dbPath);
  try {
    assert.match(String(store.db.prepare("SELECT password_hash FROM account").get()?.password_hash),/^scrypt\$/);
    const tokens=JSON.stringify(store.db.prepare("SELECT * FROM session_token").all());
    assert.equal(tokens.includes(login.sessionToken),false);
    if(process.platform!=="win32") assert.equal((await stat(dbPath)).mode&0o777,0o600);
  } finally {store.close();}
});

test("local provisioning requires explicit credentials and never resets an existing account", {timeout:30000}, async t => {
  const dir=await mkdtemp(join(tmpdir(),"team-provision-")), dbPath=join(dir,"workspace.sqlite");
  t.after(()=>rm(dir,{recursive:true,force:true}));
  const env={...process.env,TEAM_DB_PATH:dbPath,TEAM_PORT:"0",TEAM_ORG_ID:"org_provision",TEAM_BOOTSTRAP_EMAIL:"",TEAM_BOOTSTRAP_PASSWORD:""};
  const run=async(args:string[],extra:Record<string,string>={})=>{
    const child=spawn(process.execPath,["--experimental-strip-types",resolve("server/main.ts"),...args],{env:{...env,...extra},stdio:["ignore","pipe","pipe"],windowsHide:true});
    let output="",error="";child.stdout.on("data",chunk=>{output+=chunk;});child.stderr.on("data",chunk=>{error+=chunk;});
    const [code]=await once(child,"close");return {code,output,error};
  };
  const missing=await run([]);assert.equal(missing.code,1);assert.match(missing.error,/First startup requires/);
  const credentials={TEAM_ACCOUNT_EMAIL:"local@example.test",TEAM_ACCOUNT_PASSWORD:"local provision password",TEAM_ACCOUNT_NAME:"Local"};
  const created=await run(["provision-account"],credentials);assert.equal(created.code,0,created.error);
  assert.equal(created.output.includes(credentials.TEAM_ACCOUNT_PASSWORD),false);
  const before=openTeamDatabase(dbPath);const hash=before.db.prepare("SELECT password_hash FROM account").get()?.password_hash;before.close();
  const duplicate=await run(["provision-account"],{...credentials,TEAM_ACCOUNT_PASSWORD:"different local password"});assert.equal(duplicate.code,1);
  const after=openTeamDatabase(dbPath);
  try {assert.equal(after.db.prepare("SELECT count(*) AS n FROM account").get()?.n,1);assert.equal(after.db.prepare("SELECT password_hash FROM account").get()?.password_hash,hash);}
  finally {after.close();}
});
