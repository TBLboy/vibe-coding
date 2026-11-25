import { ROLE_LABELS, h, icon, loader, openDialog, tag } from "../dom.js";
import { connectGuide } from "./connect-guide.js";
import { logView } from "./log.js";
import { membersView } from "./members.js";
import { overviewView } from "./overview.js";

// Keys match TAB_KEYS in router.js.
const TABS = [
  { key: "overview", label: "概览", view: overviewView },
  { key: "log", label: "工程日志", view: logView },
  { key: "members", label: "成员与接入", view: membersView },
];

// Shown instead of any workspace data. Nothing about the workspace is rendered here.
const NO_ACCESS = {
  requested: ["你的加入申请正在等待审批", "负责人通过之前，你不能查看这个空间的任何内容。", "下一步：等待负责人处理，或回到列表查看申请状态。"],
  rejected: ["你的加入申请没有通过", "你不能查看这个空间的内容。", "下一步：联系负责人，或回到列表重新申请。"],
  invited: ["你有一条这个空间的邀请", "接受邀请之前，你还不能查看空间内容。", "下一步：回到列表，在「待处理邀请」里接受。"],
  none: ["你不是这个工作空间的成员", "只有已加入的成员可以查看空间内容。", "下一步：请负责人邀请你，或回到列表用空间 ID 申请加入。"],
  not_found: ["没有找到这个工作空间", "地址里的空间 ID 可能有误，或这个空间已不存在。", "下一步：回到列表，从已加入的空间进入。"],
};

function noAccess(kind) {
  const [title, reason, next] = NO_ACCESS[kind] ?? NO_ACCESS.none;
  return h("section", { class: "panel" },
    h("h1", { tabindex: "-1" }, title),
    h("p", null, reason),
    h("p", null, next),
    h("div", { class: "actions" },
      h("a", { class: "btn", href: "#/workspaces" }, icon("back"), h("span", { class: "btn-label" }, "返回工作空间列表"))));
}

export function workspaceView(ctx, route) {
  const { api } = ctx;
  const root = h("div", { class: "page" });
  let workspace = null;
  let tabs = null;
  let tabBody = null;
  let tabView = null;
  let currentTab = null;
  let wanted = route; // The address may change while the workspace is still loading.

  function showTab(next, moveFocus) {
    tabView?.dispose?.();
    currentTab = next.tab;
    const tab = TABS.find((item) => item.key === next.tab);
    for (const link of tabs.querySelectorAll("a")) {
      if (link.dataset.tab === tab.key) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    tabBody.setAttribute("aria-label", tab.label);
    tabView = tab.view(ctx, workspace, next);
    tabBody.replaceChildren(tabView.el);
    tabView.start();
    if (moveFocus) tabBody.focus();
  }

  const start = loader(root, () => api.getWorkspace(route.workspaceId), (box, data) => {
    workspace = data;
    ctx.setCrumb(workspace.name);
    const connect = h("button", { type: "button", class: "btn" }, "连接 OpenCode");
    connect.addEventListener("click", () => openDialog({
      title: "连接 OpenCode",
      trigger: connect,
      build: (body) => body.append(connectGuide(workspace)),
    }));
    tabs = h("nav", { class: "tabs", "aria-label": "工作空间页面" }, TABS.map((tab) =>
      h("a", { href: `#/w/${encodeURIComponent(workspace.id)}/${tab.key}`, "data-tab": tab.key }, tab.label)));
    tabBody = h("div", { class: "tab-body", role: "region", tabindex: "-1" });
    box.append(
      h("div", { class: "page-head" },
        h("div", { class: "title-line" }, h("h1", { tabindex: "-1" }, workspace.name), tag(ROLE_LABELS[workspace.role], workspace.role === "owner" ? "accent" : "neutral")),
        h("div", { class: "actions" }, connect)),
      tabs,
      tabBody);
    showTab(wanted, false);
    ctx.focusHeading();
  }, {
    renderError(error) {
      if (error.code !== "forbidden" && error.code !== "not_found") return null;
      queueMicrotask(() => ctx.focusHeading());
      return noAccess(error.code === "not_found" ? "not_found" : error.details.relation);
    },
  });

  return {
    el: root,
    start,
    /** Same workspace: switch tabs or pass the change to the current tab without reloading the shell. */
    update(next) {
      wanted = next;
      if (!workspace) return start();
      if (next.tab !== currentTab || !tabView.update) return showTab(next, true);
      return tabView.update(next);
    },
    dispose() {
      tabView?.dispose?.();
    },
  };
}
