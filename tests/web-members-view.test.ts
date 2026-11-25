import assert from "node:assert/strict";
import test from "node:test";
import { membersView } from "../web/js/views/members.js";

// Contract double only; actual geometry, focus and submissions are browser checks.
class Element {
  tag: string;
  attributes: Record<string, string> = {};
  children: Element[] = [];
  listeners: Record<string, () => unknown> = {};
  className = "";
  classList = { add: (name: string) => { this.className += ` ${name}`; } };
  private value = "";
  constructor(tag: string, text = "") { this.tag = tag; this.value = text; }
  append(...nodes: Element[]) { this.children.push(...nodes); }
  replaceChildren(...nodes: Element[]) { this.children = nodes; this.value = ""; }
  setAttribute(name: string, value: string) { this.attributes[name] = value; }
  addEventListener(name: string, listener: () => unknown) { this.listeners[name] = listener; }
  get textContent(): string { return this.value + this.children.map((child) => child.textContent).join(""); }
  set textContent(value: string) { this.children = []; this.value = value; }
}
const all = (root: Element): Element[] => [root, ...root.children.flatMap(all)];
const byClass = (root: Element, name: string) => all(root).filter((node) => node.className.split(" ").includes(name));

async function withDOM(run: () => Promise<void>) {
  const originals = ["Node", "document"].map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)] as const);
  Object.defineProperty(globalThis, "Node", { configurable: true, value: Element });
  Object.defineProperty(globalThis, "document", { configurable: true, value: {
    createElement: (tag: string) => new Element(tag),
    createElementNS: (_: string, tag: string) => new Element(tag),
    createTextNode: (text: string) => new Element("#text", text),
  } });
  try { await run(); } finally {
    for (const [name, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  }
}
const workspace = { id: "ws demo", links: ["https://example.test/reference"] };
const member = { displayName: "林舟", email: "lin@example.test", role: "member", lastSeenAt: null };

test("members owner surface integrates identity, invitations and shared placeholder guide", async () => withDOM(async () => {
  const data = { role: "owner", members: [member], pendingRequests: [], invitations: [{ email: "xu@example.test", invitedByName: "周宁", at: null }] };
  const view = membersView({ api: { getMembers: async () => data } }, workspace);
  await view.start();
  const root = view.el as unknown as Element;
  assert.deepEqual(root.children.map((node) => node.attributes["aria-label"]), ["成员管理", "连接 OpenCode"]);
  assert.equal(byClass(root, "access-member").length, 1);
  assert.equal(byClass(root, "access-requests").length, 0);
  assert.equal(all(root).filter((node) => node.tag === "table").length, 0);
  assert.ok(byClass(root, "access-identity")[0].textContent.includes("lin@example.test"));
  for (const text of ["最近活跃", "暂无记录", "没有待审批", "xu@example.test", "尚未接受，还不是成员", "TEAM_SESSION_TOKEN", "<你的账号会话>", "/reload"]) assert.ok(root.textContent.includes(text), text);
  assert.equal(byClass(root, "guide-step").length, 3);
  const repos = byClass(root, "access-repos")[0];
  assert.equal(repos.tag, "details");
  assert.equal(repos.attributes.open, undefined);
  assert.ok(repos.textContent.includes(workspace.links[0]));
}));

test("pending requests are actionable for owners only; member result omits private collections", async () => withDOM(async () => {
  for (const role of ["owner", "member"]) {
    const data = role === "owner"
      ? { role, members: [member], pendingRequests: [{ displayName: "陈默", email: "chen@example.test", accountId: "chen", at: null }], invitations: [] }
      : { role, members: [member] };
    const view = membersView({ api: { getMembers: async () => data } }, workspace);
    await view.start();
    const root = view.el as unknown as Element;
    assert.equal(byClass(root, "access-requests").length, role === "owner" ? 1 : 0);
    assert.equal(byClass(root, "access-invite").length, role === "owner" ? 1 : 0);
    assert.equal(all(root).filter((node) => node.tag === "input").length, role === "owner" ? 1 : 0);
    if (role === "member") assert.ok(root.textContent.includes("由负责人处理"));
    else assert.ok(root.textContent.includes("通过拒绝"));
  }
}));

test("members read failure retries into honest empty member and repository states", async () => withDOM(async () => {
  let fail = true;
  const view = membersView({ api: { getMembers: async () => {
    if (fail) throw Error("演示读取失败");
    return { role: "owner", members: [], pendingRequests: [], invitations: [] };
  } } }, { id: "empty", links: [] });
  await view.start();
  const root = view.el as unknown as Element;
  assert.ok(root.textContent.includes("加载失败"));
  fail = false;
  await all(root).find((node) => node.tag === "button")!.listeners.click();
  for (const text of ["暂无成员", "没有等待接受", "没有填写参考仓库"]) assert.ok(root.textContent.includes(text), text);
}));
