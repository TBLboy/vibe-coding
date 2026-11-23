import { randomUUID } from "node:crypto";
import { readdir } from "node:fs/promises";
import { validateBinding } from "../../../../core/team/binding.ts";
import { parseManifest, serializeManifest, hashContent, type Manifest } from "../../../../core/team/manifest.ts";
import { projectServerPath, unprojectLocalPath } from "../../../../core/team/projection.ts";
import { validateChanges, type Change } from "../../../../core/team/change-feed.ts";
import { routeLocalWrite, routeWriteConflict } from "../../../../core/team/write-router.ts";
import { loadCredentials, type Credentials } from "./binding.ts";
import { SafeFiles, withProjectLock, artifact } from "./files.ts";
import { TeamClient, TeamError, object } from "./client.ts";

const MANIFEST=".vibe/.sync/manifest.json";
const hash=(bytes:Buffer|null)=>bytes===null?null:hashContent(bytes);
const entryAt=(manifest:Manifest,path:string)=>Object.hasOwn(manifest.entries,path)?manifest.entries[path]:undefined;
function putEntry(manifest:Manifest,path:string,version:number,hash:string) {
  Object.defineProperty(manifest.entries,path,{value:{version,hash},enumerable:true,configurable:true,writable:true});
}
function localPath(path:string):string {const p=projectServerPath(path);return p.kind==="root"?p.relativePath:`.vibe/${p.relativePath}`;}
function contentRecord(raw:unknown,path:string) {
  const doc=object(raw);
  if(doc.path!==path||!Number.isSafeInteger(doc.version)||doc.version<1)throw new TeamError("invalid_response");
  if(doc.content===null){if(doc.hash!==null&&doc.hash!==undefined)throw new TeamError("invalid_response");return {path,version:doc.version as number,hash:null,content:null};}
  if(typeof doc.content!=="string"||Buffer.byteLength(doc.content)>1024*1024||hashContent(doc.content)!==doc.hash)throw new TeamError("invalid_content_hash");
  return {path,version:doc.version as number,hash:doc.hash as string,content:doc.content};
}
export interface SyncResult {ok:boolean;cursor:number;warnings:string[];lastError:string|null;lastSyncAt:number|null;pending:number;lag:number}
export class TeamMirror {
  readonly root:string;readonly options:{budgetMs?:number;now?:()=>number};
  readonly files:SafeFiles;
  private failures=0;private nextAttempt=0;private authToken:string|null=null;
  private credentials:Credentials|null=null;private client:TeamClient|null=null;
  private manifest:Manifest={schemaVersion:1,cursor:0,entries:{}};
  private deadline=0;private signal?:AbortSignal;private warnings=new Set<string>();
  private lastSyncAt:number|null=null;private lastError:string|null=null;private pending=0;private lag=0;
  workspace:{name:string;ownerAccountId:string;role:string}|null=null;
  constructor(root:string,options:{budgetMs?:number;now?:()=>number}={}) {this.root=root;this.options=options;this.files=new SafeFiles(root);}
  status(ok=this.lastError===null):SyncResult{return {ok,cursor:this.manifest.cursor,warnings:[...this.warnings].slice(-50),lastError:this.lastError,lastSyncAt:this.lastSyncAt,pending:this.pending,lag:this.lag};}
  private warn(message:string){this.warnings.add(message);if(this.warnings.size>100)this.warnings.delete(this.warnings.values().next().value!);}
  private check(){if(this.signal?.aborted||Date.now()>=this.deadline)throw new TeamError("budget_exhausted");}
  private async save(){await this.files.write(MANIFEST,serializeManifest(this.manifest));}
  private prefix(){return `/workspaces/${this.credentials!.workspaceId}`;}
  private request(path:string,method="GET",body?:unknown,headers:Record<string,string>={}){this.check();return this.client!.request(path,method,body,headers,this.deadline,this.signal);}
  private async current(path:string) {
    try{return contentRecord(await this.request(`${this.prefix()}/documents/${encodeURIComponent(path)}`),path);}
    catch(error){if(error instanceof TeamError&&error.status===404)return null;throw error;}
  }
  private async replace(path:string,content:string|null,version:number,hashValue:string|null) {
    this.check();const relative=localPath(path),entry=entryAt(this.manifest,path),snapshot=await this.files.read(relative);
    if(content===null) {
      if(entry&&unprojectLocalPath(relative)===path&&snapshot!==null) {
        if(hash(snapshot)!==entry.hash)this.warn(`conflict: ${await this.files.preserve(relative,snapshot)}`);
        if(hash(await this.files.read(relative))!==hash(snapshot))throw new TeamError("local_changed");
        await this.files.remove(relative,hash(snapshot)!);
      }
      delete this.manifest.entries[path];return;
    }
    if(hash(snapshot)!==hashValue) {
      if(snapshot!==null)this.warn(`conflict: ${await this.files.preserve(relative,snapshot)}`);
      if(hash(await this.files.read(relative))!==hash(snapshot))throw new TeamError("local_changed");
      this.check();await this.files.write(relative,content,hash(snapshot));
    }
    putEntry(this.manifest,path,version,hashValue!);
    if(projectServerPath(path).kind==="unmapped")this.warn(`unmapped: ${path}`);
  }
  private async candidates(check=()=>this.check()):Promise<string[]> {
    const local:string[]=[];
    for(const entry of await readdir(this.root))if(artifact(entry)||entry.startsWith(".vibe")&&entry!==".vibe")this.warn(`ignored copy: ${entry}`);
    for(const folder of [".vibe/constitution",".vibe/specs",".vibe/work",".vibe/members",".vibe/activity",".vibe/_unmapped",".opencode/skills"]){local.push(...await this.files.scan(folder,check));}
    if(await this.files.read("AGENTS.md")!==null)local.push("AGENTS.md");
    if(await this.files.read(".vibe/index.json")!==null)local.push(".vibe/index.json");
    const paths=new Set(Object.keys(this.manifest.entries));
    for(const file of local) {
      if(artifact(file)){this.warn(`ignored copy: ${file}`);continue;}
      const server=unprojectLocalPath(file);if(server)paths.add(server);else this.warn(`unmapped: ${file}`);
    }
    return [...paths].sort();
  }
  async inspect():Promise<SyncResult> {
    const bytes=await this.files.read(MANIFEST);if(!bytes)throw new TeamError("manifest_missing");
    const manifest=parseManifest(bytes.toString()),credentials=await loadCredentials(this.root),deadline=Date.now()+1500;
    const check=()=>{if(Date.now()>=deadline)throw new TeamError("budget_exhausted");};let pending=0;
    for(const path of new Set([...Object.keys(manifest.entries),...await this.candidates(check)])) {
      check();const snapshot=await this.files.read(localPath(path)),entry=entryAt(manifest,path);if(!entry&&snapshot===null)continue;
      const decision=routeLocalWrite({serverPath:path,entry,localHash:hash(snapshot),accountId:credentials.accountId,ownerAccountId:this.workspace?.ownerAccountId??null});
      if(decision.action==="push"||decision.action==="pushDelete")pending++;
    }
    return {...this.status(),cursor:manifest.cursor,pending};
  }
  private async push(paths:string[]) {
    for(const path of paths) {
      this.check();const snapshot=await this.files.read(localPath(path)),entry=entryAt(this.manifest,path);
      if(!entry&&snapshot===null)continue;
      const decision=routeLocalWrite({serverPath:path,entry,localHash:hash(snapshot),accountId:this.credentials!.accountId,ownerAccountId:this.workspace!.ownerAccountId});
      for(const warning of decision.warnings)this.warn(`${warning.code}: ${warning.message}`);
      if(decision.action==="noop"||decision.action==="ignore")continue;
      this.pending++;
      if(decision.action==="restore") {
        const doc=await this.current(path);
        if(doc)await this.replace(path,doc.content,doc.version,doc.hash);else this.warn(`untracked retained: ${path}`);
      } else {
        if(snapshot!==null&&snapshot.byteLength>1024*1024)throw new TeamError("document_too_large");
        try {
          const result=await this.request(`${this.prefix()}/documents/${encodeURIComponent(path)}`,decision.action==="pushDelete"?"DELETE":"PUT",
            decision.action==="pushDelete"?undefined:{content:new TextDecoder("utf-8",{fatal:true}).decode(snapshot!)},{"if-match":String(decision.baseVersion)});
          if(!Number.isSafeInteger(result.version)||result.version<1||result.hash!==hash(snapshot))throw new TeamError("invalid_response");
          if(snapshot===null)delete this.manifest.entries[path];else putEntry(this.manifest,path,result.version,hash(snapshot)!);
        } catch(error) {
          if(!(error instanceof TeamError)||error.status!==409)throw error;
          const doc=await this.current(path),resolution=routeWriteConflict({localHash:hash(snapshot),currentHash:doc?.hash??null,currentVersion:doc?.version??0});
          if(resolution.action==="markSynced") {
            if(snapshot===null)delete this.manifest.entries[path];else putEntry(this.manifest,path,doc!.version,doc!.hash!);
          } else if(doc) {this.warn(`conflict: ${path}`);await this.replace(path,doc.content,doc.version,doc.hash);}
          else this.warn(`untracked retained after conflict: ${path}`);
        }
      }
      await this.save();this.pending--;
    }
  }
  private async batch() {
    for(let attempt=0;attempt<2;attempt++) {
      const value=await this.request(`${this.prefix()}/changes?since=${this.manifest.cursor}&limit=200`);
      try {
        validateChanges(this.manifest.cursor,value.changes);
        if(typeof value.hasMore!=="boolean"||(value.hasMore&&value.changes.length===0))throw new TeamError("invalid_batch");
        for(const c of value.changes){if(c.op==="upsert")contentRecord(c,c.path);else if(c.content!==null&&c.content!==undefined)throw new TeamError("invalid_batch");}
        return {changes:value.changes as (Change&{content:string|null})[],hasMore:value.hasMore};
      } catch {if(attempt===1)throw new TeamError("invalid_batch");}
    }
    throw new TeamError("invalid_batch");
  }
  async sync(force=false,signal?:AbortSignal):Promise<SyncResult> {
    const now=(this.options.now??Date.now)();
    try {
      return await withProjectLock(this.root,async()=>{
        this.credentials=await loadCredentials(this.root);
        const bytes=await this.files.read(MANIFEST);if(!bytes)throw new TeamError("manifest_missing");
        try{this.manifest=parseManifest(bytes.toString());}catch{throw new TeamError("manifest_corrupt");}
        if(this.authToken&&this.authToken!==this.credentials.workspaceToken){this.authToken=null;this.nextAttempt=0;}
        if(this.authToken||(!force&&now<this.nextAttempt))return this.status(false);
        this.signal=signal;this.deadline=Date.now()+(this.options.budgetMs??1500);this.pending=0;
        this.client=new TeamClient(this.credentials.serverUrl,this.credentials.workspaceToken);
        const info=await this.request(this.prefix()),workspace=object(info.workspace);
        validateBinding({workspaceId:workspace.id,accountId:workspace.ownerAccountId,serverUrl:this.credentials.serverUrl});
        if(workspace.id!==this.credentials.workspaceId||typeof workspace.name!=="string"||!["owner","member"].includes(info.role))throw new TeamError("invalid_response");
        this.workspace={name:workspace.name,ownerAccountId:workspace.ownerAccountId,role:info.role};
        const initialized=this.manifest.cursor>0||Object.keys(this.manifest.entries).length>0;
        if(initialized)await this.push(await this.candidates());
        let hasMore=true;
        while(hasMore) {
          this.check();const batch=await this.batch();this.lag=batch.changes.length+(batch.hasMore?1:0);
          for(const change of batch.changes) {
            this.check();const known=entryAt(this.manifest,change.path);
            if(!known||known.version<change.version) {
              if(change.op==="upsert"&&!known&&await this.files.read(localPath(change.path))===null) {
                const current=await this.current(change.path);if(!current)throw new TeamError("invalid_response");
                await this.replace(change.path,current.content,current.version,current.hash);
              } else await this.replace(change.path,change.op==="delete"?null:change.content,change.version,change.hash??null);
            }
            this.manifest.cursor=change.seq;await this.save();
          }
          hasMore=batch.hasMore;this.lag=hasMore?1:0;
        }
        if(!initialized)await this.push(await this.candidates());
        this.lastSyncAt=now;this.lastError=null;this.failures=0;this.nextAttempt=0;return this.status(true);
      });
    } catch(error) {
      this.lastError=error instanceof TeamError?error.code:error instanceof Error&&/busy|symlink|collision|local_changed/iu.test(error.message)?error.message:"local_sync_failed";
      if(error instanceof TeamError&&(error.status===401||error.status===403))this.authToken=this.credentials?.workspaceToken??null;
      if(error instanceof TeamError&&["network_unavailable","budget_exhausted"].includes(error.code)||error instanceof TeamError&&error.status>=500) {
        this.nextAttempt=now+Math.min(120000,15000*2**Math.min(this.failures++,3));
      }
      return this.status(false);
    }
  }
  async recordProgress(kind:unknown,text:unknown,mode:unknown="append",signal?:AbortSignal) {
    if(!["progress","session"].includes(String(kind))||typeof text!=="string"||Buffer.byteLength(text)>1024*1024||!["append","replace"].includes(String(mode)))throw new TeamError("invalid_progress");
    await withProjectLock(this.root,async()=>{
      const credentials=await loadCredentials(this.root),path=`.vibe/members/${credentials.accountId}/${kind}.md`,old=await this.files.read(path);
      const value=mode==="replace"?text:`${old?new TextDecoder("utf-8",{fatal:true}).decode(old):""}\n## ${new Date().toISOString()}\n${text}\n`;
      if(Buffer.byteLength(value)>1024*1024)throw new TeamError("progress_too_large");await this.files.write(path,value,hash(old));
    });
    const result=await this.sync(false,signal);return {status:result.ok?"synced":"saved_locally",...result};
  }
  async task(action:"declare"|"claim"|"status",input:Record<string,unknown>,signal?:AbortSignal) {
    const credentials=await loadCredentials(this.root),client=new TeamClient(credentials.serverUrl,credentials.workspaceToken);
    const id=typeof input.id==="string"?input.id:"";
    if(action!=="declare"&&!/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/u.test(id))throw new TeamError("invalid_task_id");
    const suffix=action==="declare"?"":`/${id}/${action}`;
    return client.request(`/workspaces/${credentials.workspaceId}/tasks${suffix}`,"POST",input,{"idempotency-key":randomUUID()},Date.now()+1500,signal);
  }
}
