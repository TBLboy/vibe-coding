// The single data interface the pages depend on. This file is the mock
// implementation: it keeps one synthetic demo state in the injected storage and
// never performs a network request. Role limits are enforced here, not only by
// hiding buttons; that makes the demo honest, it is not a production security boundary.

import { DEMO_KEY_PLACEHOLDER, DEMO_PASSWORD, createSeed } from "./seed.js";

export const STORAGE_KEY = "tw-web-mock:v1";
export const LOG_LAYERS = ["constitution", "specs", "work", "members", "activity"];
export const TASK_STATUSES = ["claimed", "open", "done", "abandoned"];

const SCHEMA_VERSION = 1;
const RECENT_CHANGE_LIMIT = 50;
const MAX_LINKS = 20;

export class ApiError extends Error {
  constructor(code, message, details = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
  }
}

function fail(code, message, details) {
  throw new ApiError(code, message, details);
}

function invalid(fields) {
  fail("invalid", Object.values(fields)[0], { fields });
}

function parseEmail(value) {
  const email = String(value ?? "").trim().toLowerCase();
  if (!email) invalid({ email: "请输入邮箱。" });
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(email)) invalid({ email: "邮箱格式不正确。" });
  return email;
}

function linkProblem(url) {
  if (url.length > 2048) return "链接过长。";
  if (url.includes("://")) {
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      return "链接格式不正确。";
    }
    if (!["https:", "http:", "ssh:", "git:"].includes(parsed.protocol) || !parsed.hostname) return "只支持 https、http、ssh 或 git 链接。";
    const webLink = parsed.protocol === "https:" || parsed.protocol === "http:";
    if (parsed.password || (webLink && parsed.username)) return "链接里不能包含账号或密码。";
    return null;
  }
  return /^[^\s@:]+@[^\s:]+:.+$/u.test(url) ? null : "链接格式不正确。";
}

function publicAccount(account) {
  return { id: account.id, email: account.email, displayName: account.displayName };
}

/**
 * @param {{ storage: { getItem(key: string): string | null, setItem(key: string, value: string): void },
 *           now?: () => number, delay?: number }} options
 */
export function createMockApi({ storage, now = () => Date.now(), delay = 160 }) {
  let memory = null; // Used when the storage cannot be read or written.
  let storageUsable = true;

  function load() {
    let raw = memory;
    if (storageUsable) {
      try {
        raw = storage.getItem(STORAGE_KEY);
      } catch {
        storageUsable = false;
      }
    }
    if (raw) {
      try {
        const state = JSON.parse(raw);
        if (state && state.schemaVersion === SCHEMA_VERSION && Array.isArray(state.accounts)) return state;
      } catch {
        // Unreadable demo state is replaced by the seed below.
      }
    }
    const seed = createSeed(now());
    save(seed);
    return seed;
  }

  function save(state) {
    memory = JSON.stringify(state);
    if (!storageUsable) return;
    try {
      storage.setItem(STORAGE_KEY, memory);
    } catch {
      storageUsable = false;
    }
  }

  /** kind: "session" (no delay, no fault), "open" (no fault), "read", "submit". */
  async function call(kind, operation) {
    if (delay > 0 && kind !== "session") await new Promise((done) => setTimeout(done, delay));
    const state = load();
    if ((kind === "read" || kind === "submit") && state.faults[kind]) {
      state.faults[kind] = false;
      save(state);
      fail("unavailable", kind === "read"
        ? "这次读取没有成功（演示注入的一次性故障）。"
        : "这次提交没有成功（演示注入的一次性故障），数据没有变化。");
    }
    const result = operation(state); // Throws before any save, so a failure never leaves partial state.
    save(state);
    return result === undefined ? undefined : JSON.parse(JSON.stringify(result));
  }

  function currentAccount(state) {
    const account = state.accounts.find((item) => item.id === state.sessionAccountId);
    if (!account) fail("unauthenticated", "请先登录。");
    return account;
  }

  const accountName = (state, id) => state.accounts.find((item) => item.id === id)?.displayName ?? "未知成员";
  const findWorkspace = (state, id) => state.workspaces.find((item) => item.id === id);
  const findMembership = (state, workspaceId, accountId) =>
    state.memberships.find((item) => item.workspaceId === workspaceId && item.accountId === accountId);
  const pendingInvitation = (state, workspaceId, email) =>
    state.invitations.find((item) => item.workspaceId === workspaceId && item.email === email && item.status === "pending");

  function requireMember(state, workspaceId) {
    const account = currentAccount(state);
    const workspace = findWorkspace(state, workspaceId);
    if (!workspace) fail("not_found", "没有找到这个工作空间。");
    const membership = findMembership(state, workspaceId, account.id);
    if (membership?.status !== "active") {
      const relation = pendingInvitation(state, workspaceId, account.email) ? "invited"
        : membership?.status === "requested" ? "requested"
        : membership?.status === "rejected" ? "rejected" : "none";
      fail("forbidden", "你还不能查看这个工作空间。", { relation });
    }
    return { account, workspace, membership };
  }

  function requireOwner(state, workspaceId) {
    const context = requireMember(state, workspaceId);
    if (context.membership.role !== "owner") fail("forbidden", "只有负责人可以执行这个操作。", { relation: "member" });
    return context;
  }

  const activeMembers = (state, workspaceId) => state.memberships
    .filter((item) => item.workspaceId === workspaceId && item.status === "active")
    .sort((a, b) => (a.role === b.role ? a.at - b.at : a.role === "owner" ? -1 : 1));

  return {
    // ----- session -----
    getSession: () => call("session", (state) => {
      const account = state.accounts.find((item) => item.id === state.sessionAccountId);
      return account ? { account: publicAccount(account) } : null;
    }),

    login: ({ email, password } = {}) => call("open", (state) => {
      const fields = {};
      const address = String(email ?? "").trim().toLowerCase();
      if (!address) fields.email = "请输入邮箱。";
      if (!String(password ?? "")) fields.password = "请输入密码。";
      if (Object.keys(fields).length) invalid(fields);
      const account = state.accounts.find((item) => item.email === address);
      // The password is only compared with the displayed demo value and is never stored.
      if (!account || password !== DEMO_PASSWORD) fail("login_mismatch", "邮箱或密码不匹配。");
      state.sessionAccountId = account.id;
      return { account: publicAccount(account) };
    }),

    loginDemo: (accountId) => call("open", (state) => {
      const account = state.accounts.find((item) => item.id === accountId);
      if (!account) fail("not_found", "没有这个演示账号。");
      state.sessionAccountId = account.id;
      return { account: publicAccount(account) };
    }),

    logout: () => call("open", (state) => {
      state.sessionAccountId = null;
    }),

    listDemoAccounts: () => call("session", (state) => ({
      password: DEMO_PASSWORD,
      accounts: state.accounts.map((item) => ({ ...publicAccount(item), kind: item.kind, note: item.note })),
    })),

    // ----- my workspaces and joining -----
    listMyWorkspaces: () => call("read", (state) => {
      const account = currentAccount(state);
      const mine = state.memberships.filter((item) => item.accountId === account.id);
      const invitations = state.invitations
        .filter((item) => item.email === account.email && item.status === "pending" && findWorkspace(state, item.workspaceId))
        .map((item) => ({
          workspaceId: item.workspaceId,
          workspaceName: findWorkspace(state, item.workspaceId).name,
          invitedByName: accountName(state, item.invitedBy),
          at: item.at,
        }));
      const invited = new Set(invitations.map((item) => item.workspaceId));
      return {
        joined: mine.filter((item) => item.status === "active").map((item) => ({
          id: item.workspaceId,
          name: findWorkspace(state, item.workspaceId).name,
          role: item.role,
          memberCount: activeMembers(state, item.workspaceId).length,
        })),
        invitations,
        // One entry per workspace: a pending invitation replaces an older rejected application.
        applications: mine
          .filter((item) => (item.status === "requested" || item.status === "rejected") && !invited.has(item.workspaceId))
          .map((item) => ({
            workspaceId: item.workspaceId,
            workspaceName: findWorkspace(state, item.workspaceId).name,
            status: item.status,
            at: item.at,
            decidedAt: item.decidedAt ?? null,
          })),
      };
    }),

    createWorkspace: ({ name, links } = {}) => call("submit", (state) => {
      const account = currentAccount(state);
      const fields = {};
      const title = String(name ?? "").trim();
      if (!title) fields.name = "请填写空间名称。";
      else if (title.length > 100) fields.name = "空间名称不能超过 100 个字符。";
      const accepted = [];
      if (links !== undefined && links !== null && !Array.isArray(links)) fields.links = "仓库链接格式不正确。";
      else (links ?? []).forEach((item, index) => {
        const url = String(item ?? "").trim();
        if (!url) return;
        const problem = linkProblem(url);
        if (problem) fields[`links.${index}`] = problem;
        else if (!accepted.includes(url)) accepted.push(url);
      });
      if (accepted.length > MAX_LINKS) fields.links = `最多填写 ${MAX_LINKS} 个仓库链接。`;
      if (Object.keys(fields).length) invalid(fields);

      state.counter += 1;
      const time = now();
      const workspace = { id: `ws_demo_${1000 + state.counter}`, name: title, ownerId: account.id, createdAt: time, links: accepted };
      state.workspaces.push(workspace);
      state.memberships.push({ workspaceId: workspace.id, accountId: account.id, role: "owner", status: "active", at: time, decidedAt: time, lastSeenAt: time });
      return {
        workspace: { id: workspace.id, name: workspace.name, links: workspace.links, role: "owner" },
        demoKey: DEMO_KEY_PLACEHOLDER,
      };
    }),

    requestMembership: (workspaceId) => call("submit", (state) => {
      const account = currentAccount(state);
      const id = String(workspaceId ?? "").trim();
      if (!id) invalid({ workspaceId: "请输入工作空间 ID。" });
      const workspace = findWorkspace(state, id);
      if (!workspace) fail("not_found", "没有找到这个工作空间，请核对 ID。");
      const membership = findMembership(state, id, account.id);
      const reply = (status, existing) => ({ status, existing, workspaceId: id, workspaceName: workspace.name });
      if (membership?.status === "active") return reply("active", true);
      if (pendingInvitation(state, id, account.email)) return reply("invited", true);
      if (membership?.status === "requested") return reply("requested", true);
      const time = now();
      // A rejected application is reused, so there is never a second record for the same account.
      if (membership) Object.assign(membership, { status: "requested", at: time, decidedAt: null });
      else state.memberships.push({ workspaceId: id, accountId: account.id, role: "member", status: "requested", at: time, decidedAt: null, lastSeenAt: null });
      return reply("requested", false);
    }),

    getInvitation: (workspaceId) => call("read", (state) => {
      const account = currentAccount(state);
      const invitation = pendingInvitation(state, workspaceId, account.email);
      const workspace = findWorkspace(state, workspaceId);
      if (!invitation || !workspace) fail("invitation_not_found", "没有发给当前账号的邀请。");
      return { workspaceId, workspaceName: workspace.name, invitedByName: accountName(state, invitation.invitedBy), at: invitation.at };
    }),

    acceptInvitation: (workspaceId) => call("submit", (state) => {
      const account = currentAccount(state);
      const invitation = pendingInvitation(state, workspaceId, account.email);
      const workspace = findWorkspace(state, workspaceId);
      if (!invitation || !workspace) fail("invitation_not_found", "没有发给当前账号的邀请。");
      const time = now();
      const membership = findMembership(state, workspaceId, account.id);
      if (membership) Object.assign(membership, { role: "member", status: "active", decidedAt: time });
      else state.memberships.push({ workspaceId, accountId: account.id, role: "member", status: "active", at: time, decidedAt: time, lastSeenAt: null });
      Object.assign(invitation, { status: "accepted", decidedAt: time });
      return { status: "active", workspaceId, workspaceName: workspace.name };
    }),

    // ----- inside a workspace (active members only) -----
    getWorkspace: (workspaceId) => call("read", (state) => {
      const { workspace, membership } = requireMember(state, workspaceId);
      return {
        id: workspace.id, name: workspace.name, links: workspace.links,
        role: membership.role, ownerName: accountName(state, workspace.ownerId),
      };
    }),

    getOverview: (workspaceId) => call("read", (state) => {
      const { membership } = requireMember(state, workspaceId);
      membership.lastSeenAt = now(); // Simulated "last active": the member just opened the workspace.
      const tasks = state.tasks.filter((item) => item.workspaceId === workspaceId).sort((a, b) => b.updatedAt - a.updatedAt);
      const grouped = Object.fromEntries(TASK_STATUSES.map((status) => [status, []]));
      for (const task of tasks) {
        grouped[task.status].push({
          id: task.id, title: task.title, status: task.status, scope: task.scope, updatedAt: task.updatedAt,
          holderName: task.claimedBy ? accountName(state, task.claimedBy) : null,
          reason: task.reason ?? null,
        });
      }
      const documents = new Set(state.documents.filter((item) => item.workspaceId === workspaceId).map((item) => item.path));
      return {
        members: activeMembers(state, workspaceId).map((item) => {
          const current = tasks.find((task) => task.status === "claimed" && task.claimedBy === item.accountId);
          return {
            accountId: item.accountId, displayName: accountName(state, item.accountId), role: item.role,
            lastSeenAt: item.lastSeenAt ?? null,
            currentTask: current ? { id: current.id, title: current.title } : null,
          };
        }),
        tasks: grouped,
        // Change metadata only: who, when, what. Never document content.
        recentChanges: state.changes
          .filter((item) => item.workspaceId === workspaceId)
          .sort((a, b) => b.seq - a.seq)
          .slice(0, RECENT_CHANGE_LIMIT)
          .map((item) => ({
            seq: item.seq, path: item.path, op: item.op, at: item.at, byName: accountName(state, item.by),
            readable: item.op === "upsert" && documents.has(item.path),
          })),
      };
    }),

    getLogTree: (workspaceId) => call("read", (state) => {
      requireMember(state, workspaceId);
      const documents = state.documents.filter((item) => item.workspaceId === workspaceId).sort((a, b) => a.path.localeCompare(b.path));
      const tasks = state.tasks.filter((item) => item.workspaceId === workspaceId);
      return {
        categories: LOG_LAYERS.map((layer) => ({
          key: layer,
          files: documents.filter((item) => item.path.startsWith(`${layer}/`)).map((item) => {
            const name = item.path.slice(layer.length + 1);
            let note = "";
            if (layer === "members") note = accountName(state, name.split("/")[0]);
            if (layer === "work") note = tasks.find((task) => `work/${task.id}.json` === item.path)?.title ?? "";
            return { path: item.path, name, note, updatedAt: item.updatedAt };
          }),
        })),
      };
    }),

    getLogDocument: (workspaceId, path) => call("read", (state) => {
      requireMember(state, workspaceId);
      const document = state.documents.find((item) => item.workspaceId === workspaceId && item.path === path);
      if (!document) fail("not_found", "这个文件不存在，或已经被删除。");
      return {
        path: document.path, content: document.content, version: document.version,
        updatedAt: document.updatedAt, updatedByName: accountName(state, document.updatedBy),
      };
    }),

    getMembers: (workspaceId) => call("read", (state) => {
      const { membership } = requireMember(state, workspaceId);
      const result = {
        role: membership.role,
        members: activeMembers(state, workspaceId).map((item) => {
          const account = state.accounts.find((entry) => entry.id === item.accountId);
          return { accountId: item.accountId, displayName: account.displayName, email: account.email, role: item.role, lastSeenAt: item.lastSeenAt ?? null };
        }),
      };
      if (membership.role !== "owner") return result; // Applications and invitations are owner-only data.
      result.pendingRequests = state.memberships
        .filter((item) => item.workspaceId === workspaceId && item.status === "requested")
        .sort((a, b) => a.at - b.at)
        .map((item) => {
          const account = state.accounts.find((entry) => entry.id === item.accountId);
          return { accountId: item.accountId, displayName: account.displayName, email: account.email, at: item.at };
        });
      result.invitations = state.invitations
        .filter((item) => item.workspaceId === workspaceId && item.status === "pending")
        .sort((a, b) => a.at - b.at)
        .map((item) => ({ email: item.email, at: item.at, invitedByName: accountName(state, item.invitedBy) }));
      return result;
    }),

    inviteMember: (workspaceId, email) => call("submit", (state) => {
      const { account } = requireOwner(state, workspaceId);
      const address = parseEmail(email);
      const target = state.accounts.find((item) => item.email === address);
      const membership = target ? findMembership(state, workspaceId, target.id) : undefined;
      if (membership?.status === "active") fail("conflict", "这个账号已经是成员。");
      if (membership?.status === "requested") return { status: "already_requested", email: address };
      if (pendingInvitation(state, workspaceId, address)) return { status: "already_invited", email: address };
      const previous = state.invitations.find((item) => item.workspaceId === workspaceId && item.email === address);
      const time = now();
      if (previous) Object.assign(previous, { status: "pending", invitedBy: account.id, at: time, decidedAt: null });
      else state.invitations.push({ workspaceId, email: address, status: "pending", invitedBy: account.id, at: time, decidedAt: null });
      return { status: "invited", email: address };
    }),

    decideMembership: (workspaceId, accountId, approve) => call("submit", (state) => {
      requireOwner(state, workspaceId);
      if (typeof approve !== "boolean") invalid({ approve: "请选择通过或拒绝。" });
      const membership = findMembership(state, workspaceId, accountId);
      if (membership?.status !== "requested") fail("conflict", "这条申请已经处理过，或已不存在。");
      // A rejection is kept as its own status; the record is not deleted.
      Object.assign(membership, { status: approve ? "active" : "rejected", decidedAt: now() });
      return { status: membership.status };
    }),

    // ----- demo-only controls: not product features -----
    demo: {
      reset: () => call("open", (state) => {
        const seed = createSeed(now());
        if (seed.accounts.some((item) => item.id === state.sessionAccountId)) seed.sessionAccountId = state.sessionAccountId;
        for (const key of Object.keys(state)) delete state[key];
        Object.assign(state, seed);
      }),
      getFaults: () => call("session", (state) => ({ ...state.faults })),
      setFault: (kind, enabled) => call("session", (state) => {
        if (kind !== "read" && kind !== "submit") invalid({ kind: "未知的故障类型。" });
        state.faults[kind] = Boolean(enabled);
        return { ...state.faults };
      }),
    },
  };
}
