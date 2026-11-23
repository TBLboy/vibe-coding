import assert from "node:assert/strict";
import test from "node:test";
import { routeLocalWrite, routeWriteConflict, type LocalWriteInput } from "../runtime/core/team/write-router.ts";

const BASE = "a".repeat(64), LOCAL = "b".repeat(64);
function input(serverPath: string, extra: Partial<LocalWriteInput> = {}): LocalWriteInput {
  return { serverPath, entry: { version: 3, hash: BASE }, localHash: LOCAL, accountId: "alice", ownerAccountId: "owner", ...extra };
}

test("unchanged tracked files do not write or warn in any layer", () => {
  for (const path of ["constitution/AGENTS.md", "specs/a.md", "members/bob/progress.md", "work/t.json", "activity/a.json", "index.json", "foreign/a.md"]) {
    const result = routeLocalWrite(input(path, {localHash:BASE}));
    assert.equal(result.action,"noop"); assert.equal(result.reason,"unchanged"); assert.deepEqual(result.warnings,[]);
  }
});

test("own member namespace pushes modifications and new files with the correct base version", () => {
  for (const path of ["members/alice/progress.md", "members/alice/nested/session.md"]) {
    const tracked = routeLocalWrite(input(path));
    assert.equal(tracked.action,"push"); assert.equal(tracked.baseVersion,3);
    assert.deepEqual(tracked.warnings,[]);
    const created = routeLocalWrite(input(path,{entry:undefined}));
    assert.equal(created.action,"push"); assert.equal(created.baseVersion,0);
    const deleted = routeLocalWrite(input(path,{localHash:null}));
    assert.equal(deleted.action,"pushDelete"); assert.equal(deleted.baseVersion,3);
  }
});

test("namespace boundary denies other members even for the shared owner", () => {
  for (const path of ["members/bob/progress.md", "members/alice2/progress.md", "members/alice", "members/alice.json"]) {
    for (const extra of [{}, {entry:undefined}, {localHash:null}]) {
      const result = routeLocalWrite(input(path,{...extra,ownerAccountId:"alice"}));
      assert.equal(result.action,"restore"); assert.equal(result.warnings[0]?.code,"namespace");
      assert.equal(result.preserveLocal,extra.localHash !== null);
    }
  }
});

test("shared owner may push/create/delete constitution, skills and specs", () => {
  for (const path of ["constitution/AGENTS.md", "constitution/skills/tdd/SKILL.md", "constitution/notes.md", "specs/modules/auth.md"]) {
    assert.equal(routeLocalWrite(input(path,{accountId:"owner"})).action,"push");
    const created = routeLocalWrite(input(path,{accountId:"owner",entry:undefined}));
    assert.equal(created.action,"push"); assert.equal(created.baseVersion,0);
    assert.equal(routeLocalWrite(input(path,{accountId:"owner",localHash:null})).action,"pushDelete");
  }
});

test("non-owner shared writes restore, preserve local bytes, and identify the owner", () => {
  for (const path of ["constitution/AGENTS.md", "specs/modules/auth.md"]) {
    for (const extra of [{}, {entry:undefined}, {localHash:null}]) {
      const result = routeLocalWrite(input(path,extra));
      assert.equal(result.action,"restore"); assert.equal(result.reason,"not-owner");
      assert.equal(result.warnings[0]?.code,"not-owner");
      assert.match(result.warnings[0]!.message,/owner/); assert.match(result.warnings[0]!.message,/请联系负责人/);
      assert.equal(result.preserveLocal,extra.localHash !== null);
    }
    assert.equal(routeLocalWrite(input(path,{ownerAccountId:null})).action,"restore");
  }
});

test("server-managed layers restore for every account and never emit a push", () => {
  for (const path of ["work/t.json", "activity/ev.json", "index.json"]) {
    for (const extra of [{}, {entry:undefined}, {localHash:null}]) {
      const result = routeLocalWrite(input(path,{accountId:"owner",...extra}));
      assert.equal(result.action,"restore"); assert.equal(result.warnings[0]?.code,"server-managed");
    }
  }
});

test("unmapped changes are ignored with warning, not deleted", () => {
  for (const extra of [{}, {entry:undefined}, {localHash:null}]) {
    const result = routeLocalWrite(input("docs/unregistered-copy.md",extra));
    assert.equal(result.action,"ignore"); assert.equal(result.warnings[0]?.code,"unmapped");
  }
});

test("409 recovery recognizes response loss including deletes and never blindly retries", () => {
  for (const hash of [LOCAL,null]) {
    const result = routeWriteConflict({localHash:hash,currentHash:hash,currentVersion:4});
    assert.equal(result.action,"markSynced"); assert.equal(result.version,4); assert.equal(result.hash,hash);
    assert.deepEqual(result.warnings,[]);
  }
  for (const pair of [[LOCAL,BASE],[LOCAL,null],[null,BASE]] as const) {
    const result = routeWriteConflict({localHash:pair[0],currentHash:pair[1],currentVersion:4});
    assert.equal(result.action,"conflictCopy"); assert.equal(result.preserveLocal,pair[0] !== null);
    assert.equal(result.warnings[0]?.code,"conflict");
  }
  assert.equal(routeWriteConflict({localHash:null,currentHash:null,currentVersion:0}).action,"markSynced");
});

test("router rejects malformed facts and never mutates its input", () => {
  const original = input("members/alice/progress.md"); const snapshot = structuredClone(original);
  Object.freeze(original.entry); Object.freeze(original); routeLocalWrite(original);
  assert.deepEqual(original,snapshot);
  for (const path of ["../escape", "/specs/x", "members/alice/../bob/x"]) {
    assert.throws(() => routeLocalWrite(input(path)), /path/);
  }
  assert.throws(() => routeLocalWrite(input("members/alice/x",{accountId:"alice/evil"})), /accountId/);
  assert.throws(() => routeLocalWrite(input("specs/x",{ownerAccountId:"../bad"})), /accountId/);
  assert.throws(() => routeLocalWrite(input("specs/x",{localHash:"bad"})), /hash/);
  assert.throws(() => routeLocalWrite(input("specs/x",{entry:{version:0,hash:BASE}})), /version/);
  assert.throws(() => routeLocalWrite(input("specs/x",{entry:{version:1,hash:"bad"}})), /hash/);
  assert.throws(() => routeLocalWrite(input("specs/x",{entry:undefined,localHash:null})), /entry or a local hash/);
  assert.throws(() => routeWriteConflict({localHash:LOCAL,currentHash:BASE,currentVersion:-1}), /version/);
  assert.throws(() => routeWriteConflict({localHash:LOCAL,currentHash:BASE,currentVersion:0}), /version/);
  assert.throws(() => routeWriteConflict({localHash:LOCAL,currentHash:"bad",currentVersion:1}), /hash/);
});

test("permission matrix never pushes a changed path for an unauthorized account", () => {
  const cases = [
    {path:"members/alice/x.md",allowed:["alice"]},
    {path:"members/bob/x.md",allowed:["bob"]},
    {path:"specs/x.md",allowed:["owner"]},
    {path:"constitution/AGENTS.md",allowed:["owner"]},
    {path:"work/t.json",allowed:[]},
    {path:"activity/e.json",allowed:[]},
    {path:"index.json",allowed:[]},
  ];
  const states = [{}, {entry:undefined}, {localHash:null}];
  for (const rule of cases) for (const accountId of ["alice","bob","owner"]) for (const state of states) {
    const result = routeLocalWrite(input(rule.path,{accountId,...state}));
    const expected = rule.allowed.includes(accountId) ? (state.localHash === null ? "pushDelete" : "push") : "restore";
    assert.equal(result.action,expected,`${accountId} ${rule.path} ${JSON.stringify(state)}`);
  }
});
