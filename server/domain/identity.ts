import { randomBytes, randomUUID, createHash, scrypt, timingSafeEqual } from "node:crypto";
import type { TeamDatabase } from "../store/sqlite.ts";
import { invalid, unauthenticated, text } from "../http/errors.ts";

export const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;
export const WORKSPACE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
export interface Account { id: string; orgId: string; email: string; displayName: string }
interface AccountRow { id: string; org_id: string; email: string; display_name: string; password_hash: string; disabled_at: string | null }
export const issueSecret = (bytes = 32): string => randomBytes(bytes).toString("base64url");
export const hashToken = (secret: string): string => createHash("sha256").update(secret).digest("hex");

function derive(password: string, salt: Buffer): Promise<Buffer> {
  return new Promise((resolve,reject) => scrypt(password,salt,32,{N:32768,r:8,p:1,maxmem:64*1024*1024},(error,key)=>error?reject(error):resolve(key)));
}
function validPassword(password: unknown): password is string {
  return typeof password === "string" && password.length >= 8 && Buffer.byteLength(password) <= 1024;
}
export async function hashPassword(password: string): Promise<string> {
  if (!validPassword(password)) invalid("Invalid password: use at least 8 characters and at most 1024 UTF-8 bytes");
  const salt=randomBytes(16), key=await derive(password,salt);
  return `scrypt$32768$8$1$${salt.toString("base64url")}$${key.toString("base64url")}`;
}
export async function verifyPassword(password: string, encoded: string): Promise<boolean> {
  if (!validPassword(password) || typeof encoded !== "string") return false;
  const match=encoded.match(/^scrypt\$32768\$8\$1\$([A-Za-z0-9_-]{22})\$([A-Za-z0-9_-]{43})$/u);
  if (!match) return false;
  const salt=Buffer.from(match[1],"base64url"), expected=Buffer.from(match[2],"base64url");
  if (salt.toString("base64url")!==match[1] || expected.toString("base64url")!==match[2]) return false;
  return timingSafeEqual(await derive(password,salt),expected);
}
export function normalizeEmail(value: unknown): string {
  const email=text(value,"email",254).toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email)) invalid("Invalid email");
  return email;
}
function publicAccount(row: AccountRow): Account {
  return {id:row.id,orgId:row.org_id,email:row.email,displayName:row.display_name};
}

/** Explicit local provisioning, never an anonymous HTTP signup endpoint. */
export async function createAccount(store: TeamDatabase, input: {orgId:string; email:string; displayName:string; password:string}, now=Date.now()): Promise<Account> {
  const email=normalizeEmail(input.email), name=text(input.displayName,"displayName",100), orgId=text(input.orgId,"orgId",128);
  const passwordHash=await hashPassword(input.password), id=`acc_${randomUUID()}`;
  store.transaction(db=>{
    db.prepare("INSERT OR IGNORE INTO org (id,name,created_at) VALUES (?,?,?)").run(orgId,orgId,new Date(now).toISOString());
    db.prepare("INSERT INTO account (id,org_id,email,password_hash,display_name,created_at) VALUES (?,?,?,?,?,?)")
      .run(id,orgId,email,passwordHash,name,new Date(now).toISOString());
  });
  return {id,orgId,email,displayName:name};
}

let dummyHash: Promise<string> | undefined;
export class LoginLimiter {
  private failures = new Map<string,{count:number;pending:number;until:number}>();
  admit(key:string,now:number): boolean {
    for (const [id,item] of this.failures) if(item.until<=now && item.pending===0) this.failures.delete(id);
    const item=this.failures.get(key) ?? {count:0,pending:0,until:now+15*60*1000};
    if(item.until<=now) {item.count=0;item.until=now+15*60*1000;}
    this.failures.set(key,item);
    if(item.count+item.pending>=5) return false;
    item.pending++;return true;
  }
  fail(key:string,now:number): void {
    const item=this.failures.get(key);
    if(!item)return;
    item.pending=Math.max(0,item.pending-1);
    if(item.until<=now) {item.count=0;item.until=now+15*60*1000;}
    item.count++;
  }
  clear(key:string): void {
    const item=this.failures.get(key); if(item)item.count=0; this.release(key);
  }
  release(key:string): void {
    const item=this.failures.get(key); if(!item)return;
    item.pending=Math.max(0,item.pending-1);
    if(item.pending===0 && item.count===0) this.failures.delete(key);
  }
}
export async function login(store:TeamDatabase, orgId:string, input:Record<string,unknown>, now:number): Promise<{sessionToken:string; account:Account}> {
  const email=normalizeEmail(input.email);
  if (typeof input.password!=="string" || Buffer.byteLength(input.password)>1024) invalid("Invalid password");
  const row=store.db.prepare("SELECT * FROM account WHERE org_id=? AND email=?").get(orgId,email) as unknown as AccountRow|undefined;
  dummyHash ??= hashPassword("Dummy credential never authenticated");
  const valid=await verifyPassword(input.password,row?.password_hash || await dummyHash);
  if (!row || row.disabled_at!==null || !valid) unauthenticated();
  const current=store.db.prepare("SELECT * FROM account WHERE id=? AND org_id=? AND disabled_at IS NULL AND password_hash=?")
    .get(row.id,orgId,row.password_hash) as unknown as AccountRow|undefined;
  if(!current) unauthenticated();
  const sessionToken=issueSecret();
  store.db.prepare("INSERT INTO session_token (token_hash,account_id,created_at,expires_at) VALUES (?,?,?,?)")
    .run(hashToken(sessionToken),row.id,now,now+SESSION_TTL_MS);
  return {sessionToken,account:publicAccount(current)};
}

export function authenticateSession(store:TeamDatabase, orgId:string, token:string, now:number): Account {
  if(!/^[A-Za-z0-9_-]{43}$/u.test(token)) unauthenticated();
  const row=store.db.prepare(`SELECT a.* FROM session_token t JOIN account a ON a.id=t.account_id
    WHERE t.token_hash=? AND t.revoked_at IS NULL AND t.expires_at>? AND a.org_id=? AND a.disabled_at IS NULL`)
    .get(hashToken(token),now,orgId) as unknown as AccountRow|undefined;
  if (!row) unauthenticated();
  return publicAccount(row);
}
