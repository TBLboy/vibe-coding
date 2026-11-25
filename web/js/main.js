// Entry point: session guard, hash routing and the top bar. This is the only
// place that chooses the data implementation; every page receives `api` and
// does not know that it is a mock.

import { avatar, h, notify, runOnce, tag } from "./dom.js";
import { createMockApi } from "./mock-api.js";
import { parseRoute } from "./router.js";
import { openDemoTools } from "./views/demo-tools.js";
import { loginView } from "./views/login.js";
import { workspaceView } from "./views/workspace.js";
import { invitationView, workspacesView } from "./views/workspaces.js";

function browserStorage() {
  try {
    const storage = window.localStorage;
    storage.getItem("tw-web-mock:probe");
    return storage;
  } catch {
    // Storage is blocked: the demo still works, but state lasts only until the page is closed.
    const items = new Map();
    return { getItem: (key) => items.get(key) ?? null, setItem: (key, value) => items.set(key, value) };
  }
}

const api = createMockApi({ storage: browserStorage() });
const app = document.getElementById("app");
const topbar = h("header", { class: "topbar" });
const main = h("main", { id: "main", tabindex: "-1" });
app.append(topbar, main);

let renderRun = 0;
let current = null; // { key, view }
let crumb = null;

function go(hash) {
  if (window.location.hash === hash) render(true);
  else window.location.hash = hash;
}

function focusHeading() {
  (main.querySelector("h1") ?? main).focus();
}

function renderTopbar(session) {
  topbar.hidden = !session;
  if (!session) return topbar.replaceChildren();
  const demo = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "演示工具");
  const logout = h("button", { type: "button", class: "btn btn-quiet btn-small" }, "退出");
  const context = { api, session, sessionChanged };
  demo.addEventListener("click", () => openDemoTools(context, demo));
  logout.addEventListener("click", async () => {
    await runOnce(logout, () => api.logout());
    notify("已退出。演示数据仍然保留。");
    sessionChanged("#/login");
  });
  return topbar.replaceChildren(h("div", { class: "topbar-inner" },
    h("a", { class: "brand", href: "#/workspaces" },
      h("span", { class: "brand-mark", "aria-hidden": "true" }, "团"),
      h("span", { class: "wordmark" }, "团队工作台")),
    tag("演示模式", "demo"),
    h("nav", { class: "crumbs", "aria-label": "当前位置" },
      h("a", { href: "#/workspaces" }, "工作空间"),
      ...(crumb ? [h("span", { class: "crumb-sep", "aria-hidden": "true" }, "/"), h("span", { class: "crumb-current" }, crumb)] : [])),
    h("div", { class: "topbar-right" },
      demo,
      h("span", { class: "account", title: session.account.email }, avatar(session.account.displayName), session.account.displayName),
      logout)));
}

/** Called after login, logout, identity switch or a demo reset. */
function sessionChanged(target) {
  current = null;
  if (target) go(target);
  else render(true);
}

function mount(key, view, token) {
  current?.view.dispose?.();
  current = { key, view, token };
  main.replaceChildren(view.el);
  view.start?.();
}

async function render(force = false) {
  const run = ++renderRun;
  const route = parseRoute(window.location.hash);
  const session = await api.getSession();
  if (run !== renderRun) return;

  if (!session) {
    // Any address without a session shows the login form. Restricted data is never requested.
    crumb = null;
    renderTopbar(null);
    mount("login", loginView({ api, sessionChanged }));
    focusHeading();
    return;
  }
  if (route.name === "root" || route.name === "login") {
    window.location.replace("#/workspaces");
    return;
  }

  const key = route.name === "workspace" ? `workspace:${session.account.id}:${route.workspaceId}` : `${route.name}:${session.account.id}`;
  if (!force && current?.key === key && current.view.update) {
    current.view.update(route);
    return;
  }

  crumb = null;
  // A page replaced while its data was still loading must not touch the shared chrome.
  const token = {};
  const live = () => current?.token === token;
  const ctx = {
    api, session, sessionChanged,
    go: (hash) => { if (live()) go(hash); },
    focusHeading: () => { if (live()) focusHeading(); },
    setCrumb(name) {
      if (!live()) return;
      crumb = name;
      renderTopbar(session);
    },
  };
  renderTopbar(session);
  if (route.name === "workspaces") mount(key, workspacesView(ctx), token);
  else if (route.name === "invitation") mount(key, invitationView(ctx, route), token);
  else if (route.name === "workspace") mount(key, workspaceView(ctx, route), token);
  else {
    mount(key, {
      el: h("div", { class: "page" }, h("section", { class: "panel" },
        h("h1", { tabindex: "-1" }, "页面不存在"),
        h("p", null, "这个地址没有对应的页面。"),
        h("div", { class: "actions" }, h("a", { class: "btn", href: "#/workspaces" }, "返回工作空间列表")))),
    });
  }
  focusHeading();
}

window.addEventListener("hashchange", () => render());
document.getElementById("skip").addEventListener("click", () => main.focus());
render();
