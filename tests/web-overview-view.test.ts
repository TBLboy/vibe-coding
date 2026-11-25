import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readdirSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

import { overviewView } from "../web/js/views/overview.js";

// A small DOM contract double: verifies rendered data, semantics and actions,
// not browser layout. Real geometry is verified separately in a browser.
class Element {
  tag: string;
  attributes: Record<string, string> = {};
  children: Element[] = [];
  listeners: Record<string, () => unknown> = {};
  className = "";
  private value = "";
  constructor(tag: string, text = "") { this.tag = tag; this.value = text; }
  append(...nodes: Element[]) { this.children.push(...nodes); }
  replaceChildren(...nodes: Element[]) { this.children = nodes; this.value = ""; }
  setAttribute(name: string, value: string) { this.attributes[name] = value; }
  addEventListener(name: string, listener: () => unknown) { this.listeners[name] = listener; }
  get textContent(): string { return this.value + this.children.map((child) => child.textContent).join(""); }
  set textContent(value: string) { this.children = []; this.value = value; }
}

function all(root: Element, predicate: (element: Element) => boolean): Element[] {
  return [root, ...root.children.flatMap((child) => all(child, () => true))].filter(predicate);
}
const byClass = (root: Element, name: string) => all(root, (node) => node.className.split(" ").includes(name));

async function withDOM(run: () => Promise<void>) {
  const originals = ["Node", "document"].map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)] as const);
  Object.defineProperty(globalThis, "Node", { configurable: true, value: Element });
  Object.defineProperty(globalThis, "document", { configurable: true, value: {
    createElement: (tag: string) => new Element(tag),
    createTextNode: (text: string) => new Element("#text", text),
  } });
  try { await run(); } finally {
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  }
}

const fixture = () => ({
  members: [{ displayName: "林舟", role: "member", lastSeenAt: null, currentTask: null }],
  tasks: {
    claimed: [{ title: "支付回调", scope: ["src/payment/"], holderName: "林舟", updatedAt: null }],
    open: [{ title: "补充测试", scope: [], holderName: null, updatedAt: null }],
    done: [],
    abandoned: [{ title: "旧接口", scope: ["src/legacy/"], holderName: null, updatedAt: null, reason: "旧服务已下线" }],
  },
  recentChanges: Array.from({ length: 9 }, (_, index) => ({
    path: index === 0 ? "specs/已删除.md" : `specs/module-${index}.md`,
    byName: "林舟", op: index === 0 ? "delete" : "write", readable: index !== 0, at: null,
  })),
});

test("overview reads members, grouped task rows, safe changes and keyboard-ready disclosure", async () => withDOM(async () => {
  const view = overviewView({ api: { getOverview: async () => fixture() } }, { id: "ws demo" });
  const root = view.el as unknown as Element;
  await view.start();
  assert.deepEqual(root.children.map((node) => node.attributes["aria-label"]), ["团队成员与进展", "团队任务", "最近变更"]);
  assert.equal(byClass(root, "task-row").length, 3);
  assert.equal(byClass(root, "task-group").length, 4);
  assert.equal(byClass(root, "board").length, 0);
  assert.equal(all(byClass(root, "team-tasks")[0], (node) => ["button", "input", "select"].includes(node.tag)).length, 0);
  for (const text of ["林舟", "暂无进行中的团队任务", "支付回调", "src/payment/", "暂无持有者", "旧服务已下线", "暂无任务"]) {
    assert.ok(root.textContent.includes(text), text);
  }
  const changes = byClass(root, "changes-panel")[0];
  const toggle = all(changes, (node) => node.tag === "button")[0];
  assert.equal(byClass(changes, "change-row").length, 5);
  assert.equal(toggle.attributes["aria-expanded"], "false");
  assert.ok(toggle.textContent.includes("4"));
  assert.ok(!all(changes, (node) => node.tag === "a").some((link) => link.textContent.includes("已删除")));
  assert.ok(all(changes, (node) => node.tag === "a").every((link) => link.attributes.href.startsWith("#/w/ws%20demo/log?path=")));
  toggle.listeners.click();
  assert.equal(byClass(changes, "change-row").length, 9);
  assert.equal(toggle.attributes["aria-expanded"], "true");
  toggle.listeners.click();
  assert.equal(byClass(changes, "change-row").length, 5);
  assert.equal(toggle.textContent, "显示更早的 4 条");
}));

test("overview keeps empty states and read failures retryable without fake data", async () => withDOM(async () => {
  let fail = true;
  const data = { members: [], tasks: { claimed: [], open: [], done: [], abandoned: [] }, recentChanges: [] };
  const view = overviewView({ api: { getOverview: async () => { if (fail) throw new Error("模拟读取失败"); return data; } } }, { id: "empty" });
  const root = view.el as unknown as Element;
  await view.start();
  assert.ok(root.textContent.includes("加载失败"));
  assert.equal(byClass(root, "task-row").length, 0);
  fail = false;
  await all(root, (node) => node.tag === "button")[0].listeners.click();
  assert.ok(root.textContent.includes("这个空间还没有团队任务"));
  assert.ok(root.textContent.includes("暂无成员进展"));
  assert.ok(root.textContent.includes("还没有变更记录"));
  assert.equal(all(root, (node) => node.tag === "button").length, 0);
}));

test("all Web entry and view scripts are syntactically valid, not just the mock API", () => {
  const root = resolve(import.meta.dirname, "..", "web");
  const files = ["serve.mjs", ...["js", "js/views"].flatMap((directory) =>
    readdirSync(resolve(root, directory)).filter((file) => file.endsWith(".js")).map((file) => `${directory}/${file}`))];
  for (const file of files) {
    const result = spawnSync(process.execPath, ["--check", resolve(root, file)], { encoding: "utf8" });
    assert.equal(result.status, 0, `${file}: ${result.stderr}`);
  }
});
