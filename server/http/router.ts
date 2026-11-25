import { createServer, type IncomingMessage, type Server } from "node:http";
import { createServer as createSecureServer, type Server as SecureServer } from "node:https";
import { readFileSync } from "node:fs";
import type { TeamDatabase } from "../store/sqlite.ts";
import { CURRENT_SCHEMA_VERSION } from "../store/schema.ts";
import { assertId } from "../../shared/team-contracts/binding.ts";
import { layerOf, validateServerPath } from "../../shared/team-contracts/layout.ts";
import { login, LoginLimiter, normalizeEmail, authenticateSession, hashToken, createIdentityToken, listIdentityTokens, revokeIdentityToken, extendIdentityToken } from "../domain/identity.ts";
import { authenticateWorkspace, connectWorkspace, requireOwner, rotateTaskKey, type WorkspaceAuth } from "../domain/access.ts";
import { createWorkspace, listWorkspaces, workspaceInfo } from "../domain/workspace.ts";
import { acceptInvitation, decideMembership, inviteMember, listMembers, removeMember, requestMembership } from "../domain/membership.ts";
import { DocumentConflictError, writeDocument, deleteDocument, getDocument } from "../domain/documents.ts";
import { getChanges } from "../domain/changes.ts";
import { ApiError, bodyObject, forbidden, invalid, notFound, unauthenticated } from "./errors.ts";
import { idempotentMutation, type Reply } from "./idempotency.ts";
import { declareTask, claimTask, updateTask } from "../domain/tasks.ts";
import { getBoard, touchPresence } from "../domain/board.ts";
import { boardForm, renderBoard } from "./board.ts";

export interface RequestLog { event:"api_request"; method:string; route:string; status:number; durationMs:number }
export interface ServerOptions { orgId:string; now?:()=>number; logger?:(entry:RequestLog)=>void; tls?:{cert:string;key:string} }
const MAX_BODY=2*1024*1024;

function readBody(req:IncomingMessage,form=false): Promise<Record<string,unknown>> {
  return new Promise((resolve,reject)=>{
    let bytes=0, failed=false; const chunks:Buffer[]=[];
    req.on("data",(chunk:Buffer)=>{
      if(failed) return;
      bytes+=chunk.length;
      if(bytes>MAX_BODY) {failed=true; chunks.length=0; reject(new ApiError(413,"too_large","Request body is too large")); return;}
      chunks.push(chunk);
    });
    req.on("end",()=>{
      if(failed) return;
      try {
        if(bytes===0) {resolve({});return;}
        const text=new TextDecoder("utf-8",{fatal:true}).decode(Buffer.concat(chunks));
        if(form) {
          if(!/^application\/x-www-form-urlencoded(?:\s*;|$)/iu.test(req.headers["content-type"]??"")) throw new ApiError(400,"invalid_request","Expected a form submission");
          const fields=new URLSearchParams(text);
          for(const key of fields.keys())if(fields.getAll(key).length!==1)throw new ApiError(400,"invalid_request","Duplicate form field");
          resolve(Object.fromEntries(fields));return;
        }
        if(!/^application\/json(?:\s*;|$)/iu.test(req.headers["content-type"]??"")) throw new ApiError(400,"invalid_request","Expected application/json");
        resolve(bodyObject(JSON.parse(text)));
      } catch(error) {reject(error instanceof ApiError?error:new ApiError(400,"invalid_request","Invalid JSON body"));}
    });
    req.on("error",()=>reject(new ApiError(400,"invalid_request","Request stream failed")));
    req.on("aborted",()=>reject(new ApiError(400,"invalid_request","Request aborted")));
  });
}
function bearer(req:IncomingMessage): string {
  const value=req.headers.authorization;
  if(typeof value!=="string" || !/^Bearer [A-Za-z0-9_-]{43}$/u.test(value)) unauthenticated();
  return value.slice(7);
}
function decode(value:string): string {try{return decodeURIComponent(value);}catch{throw new ApiError(400,"invalid_request","Invalid URL encoding");}}
function identifier(value:string): string {
  const id=decode(value); try{assertId(id,"workspaceId");}catch{invalid("Invalid identifier");} return id;
}
function integer(value:string|null,field:string,fallback?:number): number {
  if(value===null && fallback!==undefined) return fallback;
  if(value===null || !/^(0|[1-9][0-9]*)$/u.test(value) || !Number.isSafeInteger(Number(value))) invalid(`Invalid ${field}`);
  return Number(value);
}
function parameter(url:URL,name:string): string|null {
  if(url.searchParams.getAll(name).length>1) throw new ApiError(400,"invalid_request",`Duplicate ${name}`);
  return url.searchParams.get(name);
}
function ifMatch(req:IncomingMessage): number {
  const value=req.headers["if-match"];
  if(typeof value!=="string") throw new ApiError(400,"invalid_request","If-Match is required");
  const match=value.match(/^(?:"(0|[1-9][0-9]*)"|(0|[1-9][0-9]*))$/u);
  if(!match || !Number.isSafeInteger(Number(match[1]??match[2]))) throw new ApiError(400,"invalid_request","Invalid If-Match");
  return Number(match[1]??match[2]);
}
function documentPath(value:string): string {
  const path=decode(value), result=validateServerPath(path);
  if(!result.ok) invalid(`Invalid document path: ${result.reason}`);
  return path;
}
function mayWrite(auth:WorkspaceAuth,path:string): void {
  const layer=layerOf(path);
  if(layer===undefined) invalid("Unmapped document path");
  if(layer==="work" || layer==="activity" || layer==="index") invalid("Document is server-managed");
  if(layer==="members" && !path.startsWith(`members/${auth.account.id}/`)) forbidden();
  if((layer==="constitution" || layer==="specs") && auth.role!=="owner") forbidden();
}

export function createTeamServer(store:TeamDatabase, options:ServerOptions): Server | SecureServer {
  const clock=options.now??Date.now, limiter=new LoginLimiter(), counters=new Map<string,number>();
  store.db.prepare("DELETE FROM idempotency WHERE created_at<=?").run(clock()-24*60*60*1000);
  const handler = async(req:IncomingMessage,res:import("node:http").ServerResponse)=>{
    const started=Date.now(), method=req.method??"GET";
    let route="not_found", reply:Reply, html:string|undefined;
    let accessed:{workspaceId:string;accountId:string}|undefined;
    try {
      const target=req.url??"/";
      if(!target.startsWith("/") || target.startsWith("//") || target.includes("#")) throw new ApiError(400,"invalid_request","Invalid request target");
      const rawPath=target.split("?")[0], url=new URL(target,"http://localhost");
      const body=["POST","PUT","DELETE"].includes(method)?await readBody(req,rawPath==="/board"):{};
      const now=clock(), orgId=options.orgId;
      const session=()=>authenticateSession(store,orgId,bearer(req),now);
      if(rawPath==="/board" && ["GET","POST"].includes(method)) {
        route="board.html";
        if(url.searchParams.has("token")) throw new ApiError(400,"invalid_request","Use the form body or Authorization header, not URL credentials");
        const workspace=method==="POST"?body.workspaceId:parameter(url,"workspaceId");
        if(method==="GET" && workspace===null)html=boardForm();
        else {
          if(typeof workspace!=="string")invalid("workspaceId is required");
          const workspaceId=identifier(workspace);
          const token=method==="POST"?body.token:bearer(req);
          if(typeof token!=="string" || !/^[A-Za-z0-9_-]{43}$/u.test(token))unauthenticated();
          const auth=authenticateWorkspace(store,orgId,token,workspaceId,now);
          html=renderBoard(workspaceInfo(store,orgId,workspaceId).name,getBoard(store,auth,now));
        }
        reply={status:200,body:null};
      } else if(rawPath==="/api/healthz" && method==="GET") {
        route="healthz";
        const count=store.db.prepare("SELECT count(*) AS n FROM workspace WHERE org_id=?").get(orgId) as {n:number};
        reply={status:200,body:{ok:true,schemaVersion:CURRENT_SCHEMA_VERSION,workspaceCount:count.n}};
      } else if(rawPath==="/api/metrics" && method==="GET") {
        route="metrics"; session(); reply={status:200,body:{apiRequests:Object.fromEntries(counters)}};
      } else if(rawPath==="/api/auth/login" && method==="POST") {
        route="auth.login";
        const email=normalizeEmail(body.email), limitKey=JSON.stringify([email,req.socket.remoteAddress??""]);
        if(!limiter.admit(limitKey,now)) throw new ApiError(429,"rate_limited","Too many failed or pending login attempts");
        try {reply={status:200,body:await login(store,orgId,body,now)}; limiter.clear(limitKey);}
        catch(error) {
          if(error instanceof ApiError && error.status===401) limiter.fail(limitKey,clock());
          else limiter.release(limitKey);
          throw error;
        }
      } else if(rawPath==="/api/connect" && method==="POST") {
        route="connect";
        // Key validity is checked before session authentication in the domain.
        const header=req.headers.authorization;
        const sessionToken=typeof header==="string" && /^Bearer [A-Za-z0-9_-]{43}$/u.test(header)?header.slice(7):"";
        reply=store.transaction(()=>{
          const auth=connectWorkspace(store,orgId,sessionToken,body.key,now);
          touchPresence(store,auth.workspaceId,auth.accountId,now);
          return {status:200,body:{workspaceToken:auth.workspaceToken,accountId:auth.accountId,workspace:workspaceInfo(store,orgId,auth.workspaceId),role:auth.role}};
        });
      } else if(rawPath==="/api/tokens" && method==="GET") {
        route="tokens.list"; const account=session();
        reply={status:200,body:{tokens:listIdentityTokens(store,account,hashToken(bearer(req)),now)}};
      } else if(rawPath==="/api/tokens" && method==="POST") {
        route="tokens.create"; const account=session();
        reply={status:201,body:createIdentityToken(store,account,body,now),oneTime:true};
      } else if(/^\/api\/tokens\/[^/]+$/u.test(rawPath) && method==="DELETE") {
        route="tokens.revoke"; const account=session(), id=identifier(rawPath.split("/")[3]);
        reply={status:200,body:revokeIdentityToken(store,account,id,now)};
      } else if(/^\/api\/tokens\/[^/]+\/extend$/u.test(rawPath) && method==="POST") {
        route="tokens.extend"; const account=session(), id=identifier(rawPath.split("/")[3]);
        reply={status:200,body:{token:extendIdentityToken(store,account,id,body,now)}};
      } else if(rawPath==="/api/workspaces" && method==="POST") {
        route="workspaces.create"; const account=session();
        if(req.headers["idempotency-key"]!==undefined) invalid("Workspace creation is not workspace-scoped; Idempotency-Key is unsupported");
        reply={status:201,body:createWorkspace(store,account,body,now),oneTime:true};
      } else if(rawPath==="/api/workspaces" && method==="GET") {
        route="workspaces.list"; reply={status:200,body:{workspaces:listWorkspaces(store,session())}};
      } else {
        const match=rawPath.match(/^\/api\/workspaces\/([^/]+)(\/.*)?$/u);
        if(!match) notFound();
        const workspaceId=identifier(match[1]), suffix=match[2]??"";
        if(suffix==="/requests" && method==="POST") {
          route="members.request"; const account=session(); workspaceInfo(store,orgId,workspaceId);
          reply=idempotentMutation(store,workspaceId,req.headers["idempotency-key"],{accountId:account.id,method,path:rawPath,body},now,
            ()=>({status:201,body:requestMembership(store,account,workspaceId,body,now)}));
        } else if(suffix==="/invitations/accept" && method==="POST") {
          route="members.accept"; const account=session(); workspaceInfo(store,orgId,workspaceId);
          reply=idempotentMutation(store,workspaceId,req.headers["idempotency-key"],{accountId:account.id,method,path:rawPath,body},now,
            ()=>({status:200,body:acceptInvitation(store,account,workspaceId,now)}));
        } else {
          const auth=authenticateWorkspace(store,orgId,bearer(req),workspaceId,now);
          accessed={workspaceId,accountId:auth.account.id};
          const mutate=(action:()=>Reply)=>store.transaction(()=>{
            const result=idempotentMutation(store,workspaceId,req.headers["idempotency-key"],
              {accountId:auth.account.id,method,path:rawPath,ifMatch:req.headers["if-match"],body},now,action);
            if(result.status>=200 && result.status<300)touchPresence(store,workspaceId,auth.account.id,now);
            accessed=undefined;return result;
          });
          if(suffix==="" && method==="GET") {
            route="workspaces.get"; reply={status:200,body:{workspace:workspaceInfo(store,orgId,workspaceId),role:auth.role}};
          } else if(suffix==="/invitations" && method==="POST") {
            route="members.invite"; requireOwner(auth);
            reply=mutate(()=>({status:201,body:inviteMember(store,auth,body,now)}));
          } else if(suffix==="/members" && method==="GET") {
            route="members.list"; reply={status:200,body:{members:listMembers(store,auth)}};
          } else if(suffix==="/keys/rotate" && method==="POST") {
            route="keys.rotate"; requireOwner(auth);
            reply=mutate(()=>({status:200,body:{taskKey:rotateTaskKey(store,auth,body.expiresAt,now)},oneTime:true}));
          } else if(/^\/members\/[^/]+\/decide$/u.test(suffix) && method==="POST") {
            route="members.decide"; requireOwner(auth); const accountId=identifier(suffix.split("/")[2]);
            reply=mutate(()=>({status:200,body:decideMembership(store,auth,accountId,body.approve,now)}));
          } else if(/^\/members\/[^/]+$/u.test(suffix) && method==="DELETE") {
            route="members.remove"; requireOwner(auth); const accountId=identifier(suffix.split("/")[2]);
            reply=mutate(()=>({status:200,body:removeMember(store,auth,accountId,now)}));
          } else if(suffix==="/tasks" && method==="POST") {
            route="tasks.declare";reply=mutate(()=>({status:201,body:declareTask(store,auth,body,now)}));
          } else if(/^\/tasks\/[^/]+\/claim$/u.test(suffix) && method==="POST") {
            route="tasks.claim";const taskId=identifier(suffix.split("/")[2]);
            reply=mutate(()=>({status:200,body:{task:claimTask(store,auth,taskId,now)}}));
          } else if(/^\/tasks\/[^/]+\/status$/u.test(suffix) && method==="POST") {
            route="tasks.update";const taskId=identifier(suffix.split("/")[2]);
            reply=mutate(()=>({status:200,body:{task:updateTask(store,auth,taskId,body,now)}}));
          } else if(suffix==="/board" && method==="GET") {
            route="board.json";reply={status:200,body:getBoard(store,auth,now)};accessed=undefined;
          } else if(suffix==="/changes" && method==="GET") {
            route="changes.list";
            const since=integer(parameter(url,"since"),"since",0), limit=integer(parameter(url,"limit"),"limit",200);
            if(limit<1 || limit>500) invalid("Invalid limit");
            reply={status:200,body:getChanges(store,{workspaceId,since,limit})};
          } else if(suffix.startsWith("/documents/") && ["GET","PUT","DELETE"].includes(method)) {
            route=`documents.${method.toLowerCase()}`; const path=documentPath(suffix.slice("/documents/".length));
            if(method==="GET") {
              const requested=parameter(url,"version"), version=requested===null?undefined:integer(requested,"version");
              if(version===0) invalid("Invalid version");
              const doc=getDocument(store,{workspaceId,path,version}); if(!doc) notFound();
              reply={status:200,body:doc};
            } else {
              mayWrite(auth,path); const expectedVersion=ifMatch(req);
              if(method==="PUT" && typeof body.content!=="string") invalid("content must be a string");
              if(method==="PUT" && Buffer.byteLength(body.content as string)>1024*1024) throw new ApiError(413,"too_large","Document is too large");
              reply=mutate(()=>({status:200,body:method==="DELETE"?
                deleteDocument(store,{workspaceId,path,accountId:auth.account.id,expectedVersion}):
                writeDocument(store,{workspaceId,path,accountId:auth.account.id,content:body.content as string,expectedVersion})}));
            }
          } else notFound();
        }
      }
      if(accessed && reply.status>=200 && reply.status<300)touchPresence(store,accessed.workspaceId,accessed.accountId,now);
    } catch(error) {
      let failure:ApiError;
      if(error instanceof ApiError) failure=error;
      else if(error instanceof DocumentConflictError) failure=new ApiError(409,"conflict",error.message,{currentVersion:error.currentVersion,currentHash:error.currentHash});
      else if(error instanceof Error && /^invalid /iu.test(error.message)) failure=new ApiError(422,"validation_failed",error.message);
      else if(error instanceof Error && error.message==="document not found") failure=new ApiError(404,"not_found","Document not found");
      else failure=new ApiError(500,"internal_error","Internal server error");
      reply={status:failure.status,body:{error:{code:failure.code,message:failure.message,...(failure.details===undefined?{}:{details:failure.details})}}};
    }
    res.writeHead(reply.status,{"content-type":html===undefined?"application/json; charset=utf-8":"text/html; charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff",
      ...(html===undefined?{}:{"content-security-policy":"default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'","referrer-policy":"no-referrer","x-frame-options":"DENY"})});
    res.end(html??JSON.stringify(reply.body));
    const counter=`${method} ${route} ${reply.status}`; counters.set(counter,(counters.get(counter)??0)+1);
    try {options.logger?.({event:"api_request",method,route,status:reply.status,durationMs:Date.now()-started});}
    catch {process.stderr.write("Team workspace request logger failed\n");}
  };
  const tuning = {requestTimeout:5000,headersTimeout:5000,keepAliveTimeout:1000,maxHeaderSize:16384};
  // TLS is opt-in; without it the server stays plain HTTP and must not be exposed publicly.
  return options.tls
    ? createSecureServer({...tuning,cert:readFileSync(options.tls.cert),key:readFileSync(options.tls.key)},handler)
    : createServer(tuning,handler);
}
