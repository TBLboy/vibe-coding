import { execFile } from "node:child_process";
import { readdir, realpath, stat } from "node:fs/promises";
import { statSync } from "node:fs";
import { resolve } from "node:path";
import { promisify } from "node:util";
import { validateBinding, assertCanBind, type Binding } from "../../../../core/team/binding.ts";
import { serializeManifest } from "../../../../core/team/manifest.ts";
import { resolveMemoryRoot } from "../../../../core/memory-root.ts";
import { SafeFiles, withProjectLock } from "./files.ts";
import { TeamClient, TeamError, object } from "./client.ts";
const exec=promisify(execFile);
export interface Credentials extends Binding {workspaceToken:string}
export async function loadBinding(root:string):Promise<Binding|null> {
  const bytes=await new SafeFiles(root).read(".vibe/.sync/binding.json");return bytes?validateBinding(JSON.parse(bytes.toString())):null;
}
export async function loadCredentials(root:string):Promise<Credentials> {
  const files=new SafeFiles(root),binding=await loadBinding(root),bytes=await files.read(".vibe/.sync/credentials.json");
  if(!binding||!bytes)throw new TeamError("credentials_missing");
  if(process.platform!=="win32"&&((await stat(await files.path(".vibe/.sync/credentials.json"))).mode&0o077)!==0)throw new TeamError("credentials_permissions");
  const raw=object(JSON.parse(bytes.toString())),validated=validateBinding(raw);
  if(JSON.stringify(binding)!==JSON.stringify(validated)||typeof raw.workspaceToken!=="string"||!/^[A-Za-z0-9_-]{43}$/u.test(raw.workspaceToken))throw new TeamError("credentials_invalid");
  return {...binding,workspaceToken:raw.workspaceToken};
}
function repoUrl(url:string):string{return url.replace(/^([^@/]+)@([^:]+):/u,"ssh://$1@$2/").replace(/\/?\.git\/?$/u,"").replace(/\/$/u,"");}
async function verifyRepositories(root:string,repos:unknown):Promise<void> {
  if(!Array.isArray(repos))throw new TeamError("invalid_response");
  const found:{url:string;branch:string}[]=[];
  for(const child of await readdir(root,{withFileTypes:true})) {
    if(!child.isDirectory()||child.name.startsWith("."))continue;
    const cwd=resolve(root,child.name);
    try {
      const top=(await exec("git",["-C",cwd,"rev-parse","--show-toplevel"],{timeout:1000,windowsHide:true})).stdout.trim();
      if(await realpath(top)!==await realpath(cwd))continue;
      const url=(await exec("git",["-C",cwd,"remote","get-url","origin"],{timeout:1000,windowsHide:true})).stdout.trim();
      const branch=(await exec("git",["-C",cwd,"symbolic-ref","--short","HEAD"],{timeout:1000,windowsHide:true})).stdout.trim();found.push({url:repoUrl(url),branch});
    } catch { /* non-repositories do not satisfy a registered repository */ }
  }
  for(const value of repos){const repo=object(value);if(typeof repo.url!=="string"||typeof repo.branch!=="string")throw new TeamError("invalid_response");
    if(!found.some(r=>r.url===repoUrl(repo.url)&&r.branch===repo.branch))throw new TeamError("repository_mismatch: clone the registered repository/branch or explicitly force");}
}
export async function connectDirectory(root:string,input:{serverUrl:string;sessionToken:string;key:string;force?:boolean},signal?:AbortSignal) {
  root=await realpath(root);
  const hasMemory=(path:string)=>{try{return statSync(resolve(path,".vibe")).isDirectory();}catch{return false;}};
  let canonical:string|null=null;
  try {const common=(await exec("git",["-C",root,"rev-parse","--path-format=absolute","--git-common-dir"],{timeout:1000,windowsHide:true})).stdout.trim();
    if(hasMemory(resolve(common,"..")))canonical=await realpath(resolve(common,".."));
  } catch { /* non-Git workspace roots use the nearest existing memory ancestor */ }
  root=canonical??resolveMemoryRoot(root,hasMemory);
  const url=validateBinding({workspaceId:"pending",accountId:"pending",serverUrl:input.serverUrl}).serverUrl;
  if(!/^[A-Za-z0-9_-]{43}$/u.test(input.sessionToken)||!/^[A-Za-z0-9_-]{32}$/u.test(input.key))throw new TeamError("invalid_credentials");
  return withProjectLock(root,async()=>{
    const existing=await loadBinding(root);
    if(existing&&existing.serverUrl!==url)throw new TeamError("directory already bound to another server");
    const result=await new TeamClient(url,input.sessionToken).request("/connect","POST",{key:input.key},{},Date.now()+1500,signal);
    const workspace=object(result.workspace),binding=validateBinding({workspaceId:workspace.id,accountId:result.accountId,serverUrl:url});
    assertCanBind(existing,binding);
    if(existing&&existing.accountId!==binding.accountId)throw new TeamError("directory already bound to another account");
    if(typeof result.workspaceToken!=="string"||!/^[A-Za-z0-9_-]{43}$/u.test(result.workspaceToken))throw new TeamError("invalid_response");
    if(!["owner","member"].includes(result.role))throw new TeamError("invalid_response");
    if(input.force!==true)await verifyRepositories(root,workspace.repos);
    const files=new SafeFiles(root);
    if(!existing){
      if(await files.read(".vibe/.sync/manifest.json"))throw new TeamError("orphaned_sync_state: retain files and inspect before binding");
      await files.write(".vibe/.sync/manifest.json",serializeManifest({schemaVersion:1,cursor:0,entries:{}}));
    }
    await files.write(".vibe/.sync/credentials.json",JSON.stringify({...binding,workspaceToken:result.workspaceToken}));
    await files.write(".vibe/.sync/binding.json",JSON.stringify(binding));
    return {workspaceId:binding.workspaceId,accountId:binding.accountId,role:result.role};
  });
}
