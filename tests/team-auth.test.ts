import assert from "node:assert/strict";
import test from "node:test";
import { createHash, scryptSync } from "node:crypto";
import { hashPassword, verifyPassword, hashToken, issueSecret, LoginLimiter, SESSION_TTL_MS, WORKSPACE_TTL_MS, TOKEN_LIFETIMES, MIN_PASSWORD_LENGTH } from "../server/domain/identity.ts";

test("scrypt hashes use approved parameters, fresh salt and timing-safe verification", async () => {
  const password = "correct horse workspace";
  const one = await hashPassword(password), two = await hashPassword(password);
  assert.match(one,/^scrypt\$32768\$8\$1\$[A-Za-z0-9_-]{22}\$[A-Za-z0-9_-]{43}$/);
  assert.notEqual(one,two);
  const fields=one.split("$");
  assert.deepEqual(Buffer.from(fields[5],"base64url"),scryptSync(password,Buffer.from(fields[4],"base64url"),32,{N:32768,r:8,p:1,maxmem:64*1024*1024}));
  assert.equal(await verifyPassword(password,one),true);
  assert.equal(await verifyPassword("incorrect password",one),false);
  for (const encoded of ["", "argon2$bad", one.replace("32768","1073741824"), one.replace(/.$/,"!")]) {
    assert.equal(await verifyPassword(password,encoded),false);
  }
  await assert.rejects(() => hashPassword("short"),/password/);
  await assert.rejects(() => hashPassword("界".repeat(400)),/password/);
});

test("token/key entropy, digest and approved TTL constants", () => {
  const token = issueSecret(), key = issueSecret(24);
  assert.equal(Buffer.from(token,"base64url").length,32);
  assert.equal(Buffer.from(key,"base64url").length,24);
  assert.notEqual(issueSecret(),token);
  assert.equal(hashToken("abc"),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  assert.equal(hashToken(token),createHash("sha256").update(token).digest("hex"));
  assert.equal(SESSION_TTL_MS,7*24*60*60*1000);
  assert.equal(WORKSPACE_TTL_MS,7*24*60*60*1000);
  assert.deepEqual(TOKEN_LIFETIMES,{day:24*60*60*1000,week:7*24*60*60*1000,month:30*24*60*60*1000,forever:null});
});

test("password length floor is 6 and hashes round-trip", async () => {
  assert.equal(MIN_PASSWORD_LENGTH,6);
  await assert.rejects(()=>hashPassword("12345"),/at least 6/);
  const encoded=await hashPassword("123456");
  assert.equal(await verifyPassword("123456",encoded),true);
  assert.equal(await verifyPassword("123457",encoded),false);
});

test("login admission reserves concurrent slots and a success cannot erase other pending work", () => {
  const limiter=new LoginLimiter(), actor="same email/IP";
  for(let i=0;i<5;i++) assert.equal(limiter.admit(actor,0),true);
  assert.equal(limiter.admit(actor,0),false);
  limiter.clear(actor);
  assert.equal(limiter.admit(actor,0),true);
  assert.equal(limiter.admit(actor,0),false);
  for(let i=0;i<5;i++) limiter.fail(actor,0);
  assert.equal(limiter.admit(actor,0),false);
  assert.equal(limiter.admit(actor,15*60*1000),true);
  limiter.release(actor);
});
