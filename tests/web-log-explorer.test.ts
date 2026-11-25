import assert from "node:assert/strict";
import test from "node:test";

import { directoryEntries } from "../web/js/views/log.js";

test("log explorer derives real folders and exact basenames without changing source metadata", () => {
  const files = [
    { path: "specs/modules/payment.md", name: "modules/payment.md", note: "支付模块" },
    { path: "specs/modules/refund.md", name: "modules/refund.md", note: "退款模块" },
    { path: "specs/api.md", name: "api.md", note: "接口" },
    { path: "specs/modules/internal/callback.md", name: "modules/internal/callback.md" },
  ];
  const before = structuredClone(files);
  const tree = directoryEntries(files, "specs");
  assert.deepEqual([...tree.folders.keys()], ["modules"]);
  assert.deepEqual(tree.files.map((file) => file.name), ["api.md"]);
  const modules = tree.folders.get("modules");
  assert.deepEqual(modules.files.map((file) => file.name), ["payment.md", "refund.md"]);
  assert.equal(modules.files[0].path, "specs/modules/payment.md");
  assert.equal(modules.files[0].note, "支付模块");
  assert.deepEqual([...modules.folders.keys()], ["internal"]);
  assert.equal(modules.folders.get("internal").files[0].name, "callback.md");
  assert.deepEqual(files, before);
});

test("log explorer preserves repeated filenames under separate member folders and literal special names", () => {
  const tree = directoryEntries([
    { path: "members/acct_lin/progress.md" },
    { path: "members/acct_zhou/progress.md" },
    { path: "members/__proto__/constructor.md" },
    { path: "members/研发协作小组/阶段验收记录.md" },
  ], "members");
  assert.equal(tree.files.length, 0);
  assert.equal(tree.folders.size, 4);
  assert.equal(tree.folders.get("acct_lin").files[0].name, "progress.md");
  assert.equal(tree.folders.get("acct_zhou").files[0].name, "progress.md");
  assert.equal(tree.folders.get("__proto__").files[0].name, "constructor.md");
  assert.equal(tree.folders.get("研发协作小组").files[0].name, "阶段验收记录.md");
  const empty = directoryEntries([], "activity");
  assert.equal(empty.folders.size, 0);
  assert.deepEqual(empty.files, []);
});
