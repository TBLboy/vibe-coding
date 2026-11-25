import assert from "node:assert/strict";
import test from "node:test";

import { LOG_LAYERS, STORAGE_KEY, TASK_STATUSES, createMockApi } from "../web/js/mock-api.js";
import { DEMO_KEY_PLACEHOLDER, DEMO_PASSWORD, SEED_WORKSPACE_ID } from "../web/js/seed.js";

const OWNER = "acct_zhou";
const MEMBER = "acct_lin";
const APPLICANT = "acct_chen";
const INVITEE = "acct_xu";
const WS = SEED_WORKSPACE_ID;

function memoryStorage() {
  const items = new Map<string, string>();
  return {
    items,
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => { items.set(key, value); },
  };
}

function setup() {
  const storage = memoryStorage();
  let clock = Date.UTC(2026, 10, 24, 2, 40);
  const api = createMockApi({ storage, now: () => (clock += 1000), delay: 0 });
  const stored = () => JSON.parse(storage.items.get(STORAGE_KEY)!);
  return { api, storage, stored };
}

/** Resolve to the rejection so its code and details can be inspected. */
async function failure(promise: Promise<unknown>, code: string) {
  try {
    await promise;
  } catch (error: any) {
    assert.equal(error.name, "ApiError");
    assert.equal(error.code, code, error.message);
    return error;
  }
  assert.fail(`expected ${code}`);
}

/** Every read a workspace page performs. None may return data to a non-member. */
async function assertNoWorkspaceAccess(api: ReturnType<typeof createMockApi>, workspaceId: string, relation: string) {
  for (const read of [
    () => api.getWorkspace(workspaceId),
    () => api.getOverview(workspaceId),
    () => api.getLogTree(workspaceId),
    () => api.getLogDocument(workspaceId, "constitution/AGENTS.md"),
    () => api.getMembers(workspaceId),
  ]) {
    const error = await failure(read(), "forbidden");
    assert.deepEqual(error.details, { relation }, "a refusal carries the relation and no workspace data");
  }
}

test("seed has an owner, an active member and two accounts that have not joined", async () => {
  const { api } = setup();
  assert.equal(await api.getSession(), null);

  await api.loginDemo(OWNER);
  assert.deepEqual((await api.listMyWorkspaces()).joined, [{ id: WS, name: "支付项目", role: "owner", memberCount: 2 }]);
  await api.loginDemo(MEMBER);
  assert.equal((await api.listMyWorkspaces()).joined[0].role, "member");

  for (const outsider of [APPLICANT, INVITEE]) {
    await api.loginDemo(outsider);
    assert.deepEqual(await api.listMyWorkspaces(), { joined: [], invitations: [], applications: [] });
    await assertNoWorkspaceAccess(api, WS, "none");
  }

  const { accounts } = await api.listDemoAccounts();
  assert.deepEqual(accounts.map((account: any) => account.kind), ["owner", "member", "applicant", "invitee"]);
  assert.ok(accounts.every((account: any) => account.email.endsWith("@example.test")));
});

test("login accepts only the displayed demo password and never stores a password", async () => {
  const { api, storage } = setup();
  const empty = await failure(api.login({ email: " ", password: "" }), "invalid");
  assert.deepEqual(Object.keys(empty.details.fields), ["email", "password"]);
  await failure(api.login({ email: "zhou.ning@example.test", password: "my-real-secret" }), "login_mismatch");
  await failure(api.login({ email: "nobody@example.test", password: DEMO_PASSWORD }), "login_mismatch");
  assert.equal(await api.getSession(), null, "a failed login leaves no session");

  const { account } = await api.login({ email: " Zhou.Ning@example.test ", password: DEMO_PASSWORD });
  assert.equal(account.id, OWNER);
  assert.deepEqual(await api.getSession(), { account });
  assert.deepEqual([...storage.items.keys()], [STORAGE_KEY], "one storage key only");
  const raw = storage.items.get(STORAGE_KEY)!;
  assert.doesNotMatch(raw, /my-real-secret|password/i);
  assert.ok(!raw.includes(DEMO_PASSWORD));

  await api.logout();
  assert.equal(await api.getSession(), null);
  await failure(api.listMyWorkspaces(), "unauthenticated");
  await failure(api.getOverview(WS), "unauthenticated");
});

test("an account creates a workspace with a required name, optional links and no branch", async () => {
  const { api, stored } = setup();
  await api.loginDemo(APPLICANT);

  const missing = await failure(api.createWorkspace({ name: "  ", links: [] }), "invalid");
  assert.ok(missing.details.fields.name);
  const badLinks = await failure(api.createWorkspace({
    name: "风控项目",
    links: ["https://user:secret@git.example.test/a.git", "not a link", "ok@git.example.test:team/repo.git", "user:pw@git.example.test:x.git"],
  }), "invalid");
  assert.deepEqual(Object.keys(badLinks.details.fields), ["links.0", "links.1", "links.3"]);
  assert.equal(stored().workspaces.length, 1, "a rejected form creates nothing");

  const nameOnly = await api.createWorkspace({ name: " 风控项目 " });
  assert.deepEqual(nameOnly.workspace, { id: "ws_demo_1001", name: "风控项目", links: [], role: "owner" });
  assert.equal(nameOnly.demoKey, DEMO_KEY_PLACEHOLDER);
  const withLinks = await api.createWorkspace({
    name: "对账项目",
    links: ["https://git.example.test/pay/recon.git", "", " git@git.example.test:pay/recon-web.git ", "https://git.example.test/pay/recon.git"],
  });
  assert.deepEqual(withLinks.workspace.links, ["https://git.example.test/pay/recon.git", "git@git.example.test:pay/recon-web.git"]);
  assert.ok(stored().workspaces.every((workspace: any) => !("branch" in workspace) && workspace.links.every((link: any) => typeof link === "string")));

  const mine = await api.listMyWorkspaces();
  assert.deepEqual(mine.joined.map((item: any) => [item.id, item.role]), [["ws_demo_1001", "owner"], ["ws_demo_1002", "owner"]]);
  assert.equal((await api.getWorkspace("ws_demo_1001")).role, "owner");
  await assertNoWorkspaceAccess(api, WS, "none"); // Owning one workspace grants nothing in another.

  // A new workspace is an empty state: the creator only, no tasks, changes or files.
  const overview = await api.getOverview("ws_demo_1001");
  assert.equal(overview.members.length, 1);
  assert.deepEqual(overview.recentChanges, []);
  assert.ok(TASK_STATUSES.every((status) => overview.tasks[status].length === 0));
  const tree = await api.getLogTree("ws_demo_1001");
  assert.deepEqual(tree.categories, LOG_LAYERS.map((key) => ({ key, files: [] })));
});

test("an invited account cannot enter until it accepts, and can afterwards", async () => {
  const { api, stored } = setup();
  await api.loginDemo(OWNER);
  await failure(api.inviteMember(WS, "not-an-email"), "invalid");
  assert.deepEqual(await api.inviteMember(WS, " Xu.An@Example.test "), { status: "invited", email: "xu.an@example.test" });
  assert.deepEqual(await api.inviteMember(WS, "xu.an@example.test"), { status: "already_invited", email: "xu.an@example.test" });
  assert.equal(stored().invitations.length, 1, "a repeated invitation adds no record");
  const ownerView = await api.getMembers(WS);
  assert.deepEqual(ownerView.invitations.map((item: any) => item.email), ["xu.an@example.test"]);
  assert.equal(ownerView.members.length, 2, "an invitation alone does not make a member");

  // Another account can neither see nor accept an invitation that is not addressed to it.
  await api.loginDemo(APPLICANT);
  assert.deepEqual((await api.listMyWorkspaces()).invitations, []);
  await failure(api.getInvitation(WS), "invitation_not_found");
  await failure(api.acceptInvitation(WS), "invitation_not_found");
  await assertNoWorkspaceAccess(api, WS, "none");

  await api.loginDemo(INVITEE);
  const before = await api.listMyWorkspaces();
  assert.deepEqual(before.joined, []);
  assert.deepEqual(before.invitations.map((item: any) => [item.workspaceId, item.workspaceName, item.invitedByName]), [[WS, "支付项目", "周宁"]]);
  await assertNoWorkspaceAccess(api, WS, "invited");
  // Applying while invited reports the invitation instead of opening a second path.
  assert.deepEqual(await api.requestMembership(WS), { status: "invited", existing: true, workspaceId: WS, workspaceName: "支付项目" });
  assert.equal(stored().memberships.length, 2);

  assert.equal((await api.acceptInvitation(WS)).status, "active");
  await failure(api.acceptInvitation(WS), "invitation_not_found");
  const after = await api.listMyWorkspaces();
  assert.deepEqual(after.joined.map((item: any) => [item.id, item.role, item.memberCount]), [[WS, "member", 3]]);
  assert.deepEqual(after.invitations, []);
  assert.equal((await api.getWorkspace(WS)).role, "member");
  assert.equal((await api.getLogDocument(WS, "constitution/AGENTS.md")).version, 1);

  await api.loginDemo(OWNER);
  await failure(api.inviteMember(WS, "xu.an@example.test"), "conflict");
});

test("an application stays pending without access until the owner approves it", async () => {
  const { api, stored } = setup();
  await api.loginDemo(APPLICANT);
  await failure(api.requestMembership("  "), "invalid");
  await failure(api.requestMembership("ws_missing"), "not_found");
  await failure(api.getWorkspace("ws_missing"), "not_found");

  assert.deepEqual(await api.requestMembership(` ${WS} `), { status: "requested", existing: false, workspaceId: WS, workspaceName: "支付项目" });
  assert.equal((await api.requestMembership(WS)).existing, true);
  assert.equal(stored().memberships.filter((item: any) => item.accountId === APPLICANT).length, 1, "a repeated application adds no record");
  const pending = await api.listMyWorkspaces();
  assert.deepEqual(pending.joined, []);
  assert.deepEqual(pending.applications.map((item: any) => [item.workspaceId, item.status]), [[WS, "requested"]]);
  await assertNoWorkspaceAccess(api, WS, "requested");

  await api.loginDemo(OWNER);
  assert.deepEqual((await api.getMembers(WS)).pendingRequests.map((item: any) => item.accountId), [APPLICANT]);
  // Inviting an account that already applied reports the application; it does not add an invitation.
  assert.equal((await api.inviteMember(WS, "chen.mo@example.test")).status, "already_requested");
  assert.equal(stored().invitations.length, 0);
  await failure(api.decideMembership(WS, APPLICANT, "yes" as any), "invalid");
  assert.deepEqual(await api.decideMembership(WS, APPLICANT, true), { status: "active" });
  await failure(api.decideMembership(WS, APPLICANT, true), "conflict");
  await failure(api.decideMembership(WS, APPLICANT, false), "conflict");
  assert.deepEqual((await api.getMembers(WS)).pendingRequests, []);

  await api.loginDemo(APPLICANT);
  const joined = await api.listMyWorkspaces();
  assert.deepEqual(joined.joined.map((item: any) => item.id), [WS]);
  assert.deepEqual(joined.applications, []);
  assert.equal((await api.getOverview(WS)).members.length, 3);
  assert.ok((await api.getLogTree(WS)).categories.some((category: any) => category.files.length > 0));
  assert.deepEqual(await api.requestMembership(WS), { status: "active", existing: true, workspaceId: WS, workspaceName: "支付项目" });
});

test("a rejection is kept as a record, grants no access and re-applying reuses it", async () => {
  const { api, stored } = setup();
  await api.loginDemo(APPLICANT);
  await api.requestMembership(WS);
  await api.loginDemo(OWNER);
  assert.deepEqual(await api.decideMembership(WS, APPLICANT, false), { status: "rejected" });
  assert.equal((await api.getMembers(WS)).members.length, 2);

  await api.loginDemo(APPLICANT);
  const rejected = await api.listMyWorkspaces();
  assert.deepEqual(rejected.joined, []);
  assert.deepEqual(rejected.applications.map((item: any) => item.status), ["rejected"]);
  await assertNoWorkspaceAccess(api, WS, "rejected");
  const records = () => stored().memberships.filter((item: any) => item.accountId === APPLICANT);
  assert.deepEqual(records().map((item: any) => item.status), ["rejected"], "the rejection is not a deletion");

  assert.deepEqual(await api.requestMembership(WS), { status: "requested", existing: false, workspaceId: WS, workspaceName: "支付项目" });
  assert.deepEqual(records().map((item: any) => item.status), ["requested"], "the same record is reused");
  await assertNoWorkspaceAccess(api, WS, "requested");

  // A later invitation replaces the rejected entry in the account's own list.
  await api.loginDemo(OWNER);
  await api.decideMembership(WS, APPLICANT, false);
  assert.equal((await api.inviteMember(WS, "chen.mo@example.test")).status, "invited");
  await api.loginDemo(APPLICANT);
  const invited = await api.listMyWorkspaces();
  assert.equal(invited.invitations.length, 1);
  assert.deepEqual(invited.applications, []);
  await api.acceptInvitation(WS);
  assert.deepEqual(records().map((item: any) => [item.status, item.role]), [["active", "member"]]);
});

test("role limits are enforced by the data interface, not only by hidden buttons", async () => {
  const { api, stored } = setup();
  await api.loginDemo(APPLICANT);
  await api.requestMembership(WS);
  const before = JSON.stringify({ ...stored(), sessionAccountId: null });

  await api.loginDemo(MEMBER);
  const memberView = await api.getMembers(WS);
  assert.equal(memberView.role, "member");
  assert.equal("pendingRequests" in memberView, false, "applications are owner-only data");
  assert.equal("invitations" in memberView, false);
  assert.deepEqual((await failure(api.inviteMember(WS, "xu.an@example.test"), "forbidden")).details, { relation: "member" });
  await failure(api.decideMembership(WS, APPLICANT, true), "forbidden");

  for (const outsider of [APPLICANT, INVITEE]) {
    await api.loginDemo(outsider);
    await failure(api.inviteMember(WS, "xu.an@example.test"), "forbidden");
    await failure(api.decideMembership(WS, APPLICANT, true), "forbidden");
  }
  assert.equal(JSON.stringify({ ...stored(), sessionAccountId: null }), before, "refused operations change nothing");
});

test("the overview is read-only metadata and its changes link only to readable files", async () => {
  const { api } = setup();
  await api.loginDemo(MEMBER);
  const overview = await api.getOverview(WS);

  assert.deepEqual(overview.members.map((item: any) => [item.displayName, item.role, item.currentTask?.title ?? null]),
    [["周宁", "owner", "对账任务调度"], ["林舟", "member", "支付回调联调"]]);
  assert.ok(overview.members.every((item: any) => typeof item.lastSeenAt === "number"));
  assert.deepEqual(Object.keys(overview.tasks), TASK_STATUSES);
  assert.deepEqual(TASK_STATUSES.map((status) => overview.tasks[status].length), [2, 2, 1, 1]);
  assert.equal(overview.tasks.claimed[0].holderName, "林舟");
  assert.equal(overview.tasks.open[0].holderName, null);
  assert.ok(overview.tasks.abandoned[0].reason);

  assert.ok(overview.recentChanges.length > 0);
  assert.deepEqual(overview.recentChanges.map((item: any) => item.seq), [...overview.recentChanges.map((item: any) => item.seq)].sort((a, b) => b - a));
  assert.ok(overview.recentChanges.every((item: any) => !("content" in item)), "changes are metadata, not file content");
  for (const change of overview.recentChanges) {
    if (change.readable) assert.equal((await api.getLogDocument(WS, change.path)).path, change.path);
    else await failure(api.getLogDocument(WS, change.path), "not_found");
  }
  const removed = overview.recentChanges.filter((item: any) => item.op === "delete");
  assert.deepEqual(removed.map((item: any) => [item.path, item.readable]), [["specs/modules/legacy-gateway.md", false]]);
  // The file was written before it was deleted; that earlier change must not become a dead link either.
  assert.ok(overview.recentChanges.filter((item: any) => item.path === "specs/modules/legacy-gateway.md").every((item: any) => !item.readable));

  // The web has no task write operation of any kind, and no document write either.
  const operations = [...Object.keys(api), ...Object.keys(api.demo)];
  assert.deepEqual(operations.filter((name) => /task|claim|declare|write|update|put|delete|remove|rotate/i.test(name)), []);
});

test("the log tree always lists the five categories and returns stored text unchanged", async () => {
  const { api } = setup();
  await api.loginDemo(OWNER);
  const tree = await api.getLogTree(WS);
  assert.deepEqual(tree.categories.map((category: any) => category.key), ["constitution", "specs", "work", "members", "activity"]);
  const files = Object.fromEntries(tree.categories.map((category: any) => [category.key, category.files]));
  assert.deepEqual(files.activity, [], "an empty category is kept");
  assert.deepEqual(files.specs.map((file: any) => file.name), ["api-conventions.md", "modules/payment-callback.md", "modules/refund.md"]);
  assert.deepEqual(files.members.map((file: any) => [file.name, file.note]), [["acct_lin/progress.md", "林舟"], ["acct_zhou/progress.md", "周宁"]]);
  assert.equal(files.work.length, 6);
  assert.ok(files.work.every((file: any) => file.note), "task files carry their task title");

  for (const category of tree.categories) {
    for (const file of category.files) assert.equal((await api.getLogDocument(WS, file.path)).path, file.path);
  }
  const conventions = await api.getLogDocument(WS, "specs/api-conventions.md");
  assert.match(conventions.content, /<script>alert\(/, "markup in a document is returned as plain text for inert rendering");
  assert.equal((await api.getLogDocument(WS, "specs/modules/payment-callback.md")).version, 2);
  await failure(api.getLogDocument(WS, "specs/modules/legacy-gateway.md"), "not_found");
  await failure(api.getLogDocument(WS, "../secret"), "not_found");
});

test("an injected failure happens once, changes nothing and succeeds on retry", async () => {
  const { api, stored } = setup();
  await api.loginDemo(OWNER);

  assert.deepEqual(await api.demo.setFault("read", true), { read: true, submit: false });
  await failure(api.getOverview(WS), "unavailable");
  assert.deepEqual(await api.demo.getFaults(), { read: false, submit: false });
  assert.equal((await api.getOverview(WS)).members.length, 2);

  await api.demo.setFault("submit", true);
  await api.listMyWorkspaces(); // A read does not consume the submit failure.
  await failure(api.createWorkspace({ name: "风控项目" }), "unavailable");
  assert.equal(stored().workspaces.length, 1, "a failed submission leaves no partial result");
  assert.equal((await api.createWorkspace({ name: "风控项目" })).workspace.id, "ws_demo_1001");
  assert.equal(stored().workspaces.length, 2);

  await api.demo.setFault("submit", true);
  await failure(api.inviteMember(WS, "xu.an@example.test"), "unavailable");
  assert.equal(stored().invitations.length, 0);
  assert.equal((await api.inviteMember(WS, "xu.an@example.test")).status, "invited");
  await failure(api.demo.setFault("other", true), "invalid");
});

test("one demo state is shared by all identities, survives a reload and can be restored", async () => {
  const { api, storage, stored } = setup();
  await api.loginDemo(OWNER);
  await api.createWorkspace({ name: "风控项目" });
  await api.inviteMember("ws_demo_1001", "xu.an@example.test");
  await api.logout();
  await api.loginDemo(INVITEE);
  assert.equal((await api.listMyWorkspaces()).invitations[0].workspaceName, "风控项目", "switching identity keeps business data");

  // A page reload is a new interface instance over the same storage.
  const reloaded = createMockApi({ storage, delay: 0 });
  assert.equal((await reloaded.getSession()).account.id, INVITEE);
  assert.equal((await reloaded.listMyWorkspaces()).invitations.length, 1);

  await reloaded.demo.reset();
  assert.equal((await reloaded.getSession()).account.id, INVITEE, "restoring seed data keeps the demo identity");
  assert.deepEqual(await reloaded.listMyWorkspaces(), { joined: [], invitations: [], applications: [] });
  assert.equal(stored().workspaces.length, 1);

  // Unreadable or foreign stored state is replaced by the seed instead of breaking the page.
  for (const broken of ["{not json", JSON.stringify({ schemaVersion: 999, accounts: [] }), "null"]) {
    storage.items.set(STORAGE_KEY, broken);
    const fresh = createMockApi({ storage, delay: 0 });
    assert.equal(await fresh.getSession(), null);
    await fresh.loginDemo(OWNER);
    assert.equal((await fresh.listMyWorkspaces()).joined[0].id, WS);
  }
});

test("the demo keeps working in memory when browser storage is unavailable", async () => {
  const blocked = {
    getItem: () => { throw new Error("blocked"); },
    setItem: () => { throw new Error("blocked"); },
  };
  const api = createMockApi({ storage: blocked, delay: 0 });
  await api.loginDemo(OWNER);
  await api.createWorkspace({ name: "风控项目" });
  assert.equal((await api.listMyWorkspaces()).joined.length, 2);
});

test("results are copies: a page cannot change demo state by mutating what it received", async () => {
  const { api } = setup();
  await api.loginDemo(OWNER);
  const overview = await api.getOverview(WS);
  overview.tasks.open.length = 0;
  overview.members[0].role = "member";
  const again = await api.getOverview(WS);
  assert.equal(again.tasks.open.length, 2);
  assert.equal(again.members[0].role, "owner");
});

test("calls resolve asynchronously after the configured delay", async () => {
  const api = createMockApi({ storage: memoryStorage(), delay: 20 });
  let settled = false;
  const pending = api.loginDemo(OWNER).then(() => { settled = true; });
  await Promise.resolve();
  assert.equal(settled, false);
  await pending;
  assert.equal(settled, true);
});
