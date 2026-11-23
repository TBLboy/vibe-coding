import type { TeamDatabase } from "../store/sqlite.ts";
import { hashToken } from "../domain/identity.ts";
import { conflict, invalid } from "./errors.ts";

export interface Reply { status:number; body:unknown; oneTime?:boolean }
export function idempotentMutation(store:TeamDatabase, workspaceId:string, key:unknown, request:unknown, now:number, action:()=>Reply): Reply {
  if(key===undefined) return action();
  if(typeof key!=="string" || !/^[\x21-\x7e]{1,128}$/u.test(key)) invalid("Invalid Idempotency-Key");
  const requestHash=hashToken(JSON.stringify(request));
  return store.transaction(db=>{
    let existing=db.prepare("SELECT request_hash,status,response_json,created_at FROM idempotency WHERE workspace_id=? AND key=?")
      .get(workspaceId,key) as {request_hash:string;status:number;response_json:string;created_at:number}|undefined;
    if(existing && existing.created_at<=now-24*60*60*1000) {
      db.prepare("DELETE FROM idempotency WHERE workspace_id=? AND key=?").run(workspaceId,key); existing=undefined;
    }
    if(existing) {
      if(existing.request_hash!==requestHash) conflict("Idempotency-Key was used for another request");
      return {status:existing.status,body:JSON.parse(existing.response_json)};
    }
    const result=action();
    // Key/token plaintext is one-time and must never be cached in the database.
    const replay=result.oneTime?{status:409,body:{error:{code:"conflict",message:"One-time credential response unavailable; use a new request key to rotate again"}}}:result;
    db.prepare("INSERT INTO idempotency (workspace_id,key,request_hash,status,response_json,created_at) VALUES (?,?,?,?,?,?)")
      .run(workspaceId,key,requestHash,replay.status,JSON.stringify(replay.body),now);
    return result;
  });
}
