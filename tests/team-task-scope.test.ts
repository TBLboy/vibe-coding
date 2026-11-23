import assert from "node:assert/strict";
import test from "node:test";
import { normalizeScope, findScopeOverlaps } from "../runtime/core/team/task-scope.ts";

test("scope normalization canonicalizes separators/leading ./ and returns a sorted set", () => {
  const scope = [" ./src\\auth\\ ", "src//auth/login.ts", "././src/auth/", " README.md "];
  const snapshot = [...scope]; Object.freeze(scope);
  assert.deepEqual(normalizeScope(scope),["README.md","src/auth/","src/auth/login.ts"]);
  assert.deepEqual(scope,snapshot);
  assert.deepEqual(normalizeScope(normalizeScope(scope)),normalizeScope(scope));
});

test("BR-11 directory/file overlap warns in either direction", () => {
  assert.deepEqual(findScopeOverlaps(["src/auth/"],["src/auth/login.ts"]),[
    {left:"src/auth/",right:"src/auth/login.ts",reason:"directory-prefix"},
  ]);
  assert.deepEqual(findScopeOverlaps(["src/auth/login.ts"],["src/auth/"]),[
    {left:"src/auth/login.ts",right:"src/auth/",reason:"directory-prefix"},
  ]);
});

test("scope overlaps cover exact files, equal directories and nested directory prefixes", () => {
  assert.deepEqual(findScopeOverlaps(["src/auth.ts"],["./src/auth.ts"]),[
    {left:"src/auth.ts",right:"src/auth.ts",reason:"same-path"},
  ]);
  assert.deepEqual(findScopeOverlaps(["src/"],["src/"]),[
    {left:"src/",right:"src/",reason:"same-path"},
  ]);
  assert.deepEqual(findScopeOverlaps(["src/"],["src/auth/"]),[
    {left:"src/",right:"src/auth/",reason:"directory-prefix"},
  ]);
});

test("exact files are not directory prefixes and similar sibling names do not overlap", () => {
  for (const pair of [["src/auth/","src/authentication/login.ts"],["src/auth.ts","src/auth.tsx"],["src/auth","src/auth/login.ts"],["src/a/","src/b/"]]) {
    assert.deepEqual(findScopeOverlaps([pair[0]],[pair[1]]),[]);
  }
  assert.deepEqual(findScopeOverlaps([],["src/"]),[]);
  assert.deepEqual(findScopeOverlaps(["src/"],[]),[]);
});

test("scope pair output is deterministic and duplicates are suppressed", () => {
  const left = ["src/","src/","README.md"], right = ["src/z.ts","README.md","src/a.ts"];
  const result = findScopeOverlaps(left,right);
  assert.equal(result.length,3);
  assert.deepEqual(result,findScopeOverlaps([...left].reverse(),[...right].reverse()));
});

test("scope rejects invalid/escaping/absolute paths and excessive limits", () => {
  assert.throws(() => normalizeScope([null as unknown as string]), /scope/);
  assert.throws(() => normalizeScope(new Array<string>(1)), /scope/);
  for (const path of ["", " ", ".", "./", "../secret", "src/../secret", "src/./a", "/src/a", "C:\\src\\a", "\\\\server\\share", "src/\u0000a"]) {
    assert.throws(() => normalizeScope([path]), /scope|path/);
  }
  assert.throws(() => normalizeScope(Array.from({length:201},(_,i) => `src/${i}`)), /200/);
  assert.throws(() => normalizeScope([Array.from({length:5},() => "a".repeat(210)).join("/")]), /long/);
  assert.throws(() => normalizeScope([`src/${"界".repeat(86)}`]), /segment|long/);
  assert.doesNotThrow(() => normalizeScope([`src/${"界".repeat(85)}`]));
  const atLimit = ["a".repeat(255),"b".repeat(255),"c".repeat(255),"d".repeat(254),"e"].join("/");
  assert.equal(Buffer.byteLength(atLimit),1024);
  assert.deepEqual(normalizeScope([atLimit]),[atLimit]);
  assert.throws(() => normalizeScope([`${atLimit}/`]), /long/);
  assert.doesNotThrow(() => normalizeScope(Array.from({length:200},(_,i) => `src/${i}`)));
});
