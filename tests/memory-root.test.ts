import assert from "node:assert/strict";
import test from "node:test";
import { parentDirectory, resolveMemoryRoot } from "../runtime/core/memory-root.ts";

const owns = (roots: string[]) => (candidate: string) => roots.includes(candidate);

test("memory root is the nearest ancestor that already owns .vibe", () => {
  const has = owns(["/home/u/project"]);
  assert.equal(resolveMemoryRoot("/home/u/project/sub/worktree", has), "/home/u/project");
  assert.equal(resolveMemoryRoot("/home/u/project", has), "/home/u/project");
});

test("a sub-directory that already has its own .vibe wins over the project root (closest ancestor)", () => {
  const has = owns(["/home/u/project", "/home/u/project/sub"]);
  assert.equal(resolveMemoryRoot("/home/u/project/sub/x", has), "/home/u/project/sub");
});

test("without any .vibe ancestor the start directory is the fresh project root", () => {
  assert.equal(resolveMemoryRoot("/home/u/new", () => false), "/home/u/new");
  assert.throws(() => resolveMemoryRoot("  ", () => false));
});

test("parent resolution stops at the filesystem root on POSIX and Windows", () => {
  assert.equal(parentDirectory("/a/b"), "/a");
  assert.equal(parentDirectory("/a"), "/");
  assert.equal(parentDirectory("/"), "/");
  assert.equal(parentDirectory("C:\\proj\\sub"), "C:\\proj");
  assert.equal(parentDirectory("C:\\proj"), "C:\\");
  assert.equal(parentDirectory("C:\\"), "C:\\");
  assert.equal(resolveMemoryRoot("C:\\proj\\sub", (c) => c === "C:\\proj"), "C:\\proj");
  assert.equal(resolveMemoryRoot("/x/y/z", () => false), "/x/y/z");
});
