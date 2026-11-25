import { randomBytes, randomUUID, createHash, scrypt, timingSafeEqual } from "node:crypto";
import type { TeamDatabase } from "../store/sqlite.ts";
import { invalid, notFound, unauthenticated, text } from "../http/errors.ts";

export const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;
export const WORKSPACE_TTL_MS = 7 * 24 * 60 * 60 * 1000;
/** Offered lifetimes for a self-managed identity token; null is permanent. */
export const TOKEN_LIFETIMES = {day:24*60*60*1000,week:7*24*60*60*1000,month:30*24*60*60*1000,forever:null} as const;
export type TokenLifetime = keyof typeof TOKEN_LIFETIMES;
export interface IdentityToken {
  id: string; name: string; createdAt: string; expiresAt: string | null;
  lastUsedAt: string | null; current: boolean;
}
export interface TokenRow {
  id: string; token_hash: string; account_id: string; name: string;
  created_at: number; expires_at: number | null; last_used_at: number | null; revoked_at: number | null;
}
const iso = (value: number | null): string | null => value === null ? null : new Date(value).toISOString();

function lifetime(value: unknown): number | null {
  if (typeof value !== "string" || !Object.hasOwn(TOKEN_LIFETIMES, value)) {
    invalid("expiresIn must be one of: day, week, month, forever");
  }
  return TOKEN_LIFETIMES[value as TokenLifetime];
}

function issueIdentityToken(store: TeamDatabase, accountId: string, name: string, lifetimeMs: number | null, now: number): {token: IdentityToken; secret: string} {
  const secret = issueSecret(), id = `tok_${randomUUID()}`;
  const expiresAt = lifetimeMs === null ? null : now + lifetimeMs;
  store.db.prepare("INSERT INTO session_token (id,token_hash,account_id,name,created_at,expires_at) VALUES (?,?,?,?,?,?)")
    .run(id, hashToken(secret), accountId, name, now, expiresAt);
  return {token: {id, name, createdAt: iso(now)!, expiresAt: iso(expiresAt), lastUsedAt: null, current: false}, secret};
}

/** A user-managed identity token. The plaintext secret is returned only once. */
export function createIdentityToken(store: TeamDatabase, account: Account, body: Record<string, unknown>, now: number): {token: IdentityToken; secret: string} {
  const name = text(body.name, "name", 100), lifetimeMs = lifetime(body.expiresIn);
  return issueIdentityToken(store, account.id, name, lifetimeMs, now);
}

export function listIdentityTokens(store: TeamDatabase, account: Account, currentTokenHash: string, now: number): IdentityToken[] {
  const rows = store.db.prepare(`SELECT * FROM session_token WHERE account_id=? AND revoked_at IS NULL
    AND (expires_at IS NULL OR expires_at>?) ORDER BY created_at DESC, id`).all(account.id, now) as unknown as TokenRow[];
  return rows.map(row => ({
    id: row.id, name: row.name, createdAt: iso(row.created_at)!, expiresAt: iso(row.expires_at),
    lastUsedAt: iso(row.last_used_at), current: row.token_hash === currentTokenHash,
  }));
}

export function revokeIdentityToken(store: TeamDatabase, account: Account, id: string, now: number): {status: "revoked"} {
  const result = store.db.prepare("UPDATE session_token SET revoked_at=? WHERE id=? AND account_id=? AND revoked_at IS NULL")
    .run(now, id, account.id);
  if (result.changes === 0) notFound();
  return {status: "revoked"};
}

/** Extend only forward. A permanent token has no expiry to extend. */
export function extendIdentityToken(store: TeamDatabase, account: Account, id: string, body: Record<string, unknown>, now: number): IdentityToken {
  const lifetimeMs = lifetime(body.expiresIn);
  if (lifetimeMs === null) invalid("Use expiresIn day, week or month to extend; permanent tokens have no expiry");
  const row = store.db.prepare("SELECT * FROM session_token WHERE id=? AND account_id=? AND revoked_at IS NULL")
    .get(id, account.id) as unknown as TokenRow | undefined;
  if (!row) notFound();
  if (row.expires_at === null) invalid("Permanent tokens have no expiry to extend");
  const extended = Math.max(row.expires_at, now) + lifetimeMs;
  store.db.prepare("UPDATE session_token SET expires_at=? WHERE id=?").run(extended, id);
  return {id: row.id, name: row.name, createdAt: iso(row.created_at)!, expiresAt: iso(extended), lastUsedAt: iso(row.last_used_at), current: false};
}

export function touchIdentityToken(store: TeamDatabase, tokenHash: string, now: number): void {
  store.db.prepare("UPDATE session_token SET last_used_at=? WHERE token_hash=? AND (last_used_at IS NULL OR last_used_at<?)")
    .run(now, tokenHash, now - 60_000);
}

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
  store.db.prepare("INSERT INTO session_token (id,token_hash,account_id,name,created_at,expires_at) VALUES (?,?,?,?,?,?)")
    .run(`tok_${randomUUID()}`,hashToken(sessionToken),row.id,"Login token",now,now+SESSION_TTL_MS);
  return {sessionToken,account:publicAccount(current)};
}

export function authenticateSession(store:TeamDatabase, orgId:string, token:string, now:number): Account {
  if(!/^[A-Za-z0-9_-]{43}$/u.test(token)) unauthenticated();
  const hash = hashToken(token);
  const row=store.db.prepare(`SELECT a.* FROM session_token t JOIN account a ON a.id=t.account_id
    WHERE t.token_hash=? AND t.revoked_at IS NULL AND (t.expires_at IS NULL OR t.expires_at>?) AND a.org_id=? AND a.disabled_at IS NULL`)
    .get(hash,now,orgId) as unknown as AccountRow|undefined;
  if (!row) unauthenticated();
  touchIdentityToken(store, hash, now);
  return publicAccount(row);
}
