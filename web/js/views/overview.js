import { ROLE_LABELS, avatar, emptyState, formatTime, h, loader, tag } from "../dom.js";

const TASK_GROUPS = [
  { status: "claimed", label: "进行中", tone: "accent" },
  { status: "open", label: "待领取", tone: "pending" },
  { status: "done", label: "完成", tone: "ok" },
  { status: "abandoned", label: "放弃", tone: "neutral" },
];

const LAYER_ACTIONS = {
  constitution: "更新了团队规范",
  specs: "更新了规格",
  work: "更新了任务记录",
  members: "更新了进度",
  activity: "记录了活动",
};

// The newest changes are enough for a glance; the rest sits behind one control.
const CHANGES_SHOWN = 5;

function changeAction(change) {
  if (change.op === "delete") return "删除了文件";
  return LAYER_ACTIONS[change.path.split("/")[0]] ?? "更新了文件";
}

function memberRow(member) {
  return h("li", { class: "person" },
    avatar(member.displayName, "md"),
    h("div", { class: "person-body" },
      h("div", { class: "row-main" },
        h("span", { class: "row-title" }, member.displayName),
        tag(ROLE_LABELS[member.role], member.role === "owner" ? "accent" : "neutral")),
      h("p", { class: "row-meta" }, `最近活跃 ${formatTime(member.lastSeenAt)}`)),
    member.currentTask
      ? h("p", { class: "person-task" }, tag("进行中", "accent"), h("span", null, member.currentTask.title))
      : h("p", { class: "person-task person-task-idle" }, "暂无进行中的团队任务"));
}

function taskRow(task) {
  return h("li", { class: "task-row" },
    h("div", { class: "task-detail" },
      h("p", { class: "task-title" }, task.title),
      task.scope.length ? h("p", { class: "task-scope" }, task.scope.map((path) => h("code", null, path))) : null,
      task.reason ? h("p", { class: "task-reason" }, `放弃原因：${task.reason}`) : null),
    task.holderName
      ? h("span", { class: "task-holder" }, avatar(task.holderName), task.holderName)
      : h("span", { class: "task-holder task-holder-none" }, "暂无持有者"),
    h("span", { class: "task-time", "aria-label": `更新时间 ${formatTime(task.updatedAt)}` }, formatTime(task.updatedAt)));
}

function changesPanel(workspaceId, changes) {
  const list = h("ol", { class: "change-list" });
  const toggle = h("button", { type: "button", class: "btn btn-small", "aria-expanded": "false" });
  let expanded = false;

  function draw() {
    const shown = expanded ? changes : changes.slice(0, CHANGES_SHOWN);
    list.replaceChildren(...shown.map((change) => h("li", { class: "change-row" },
      h("div", { class: "change-detail" },
        h("p", { class: "event-line" }, h("strong", null, change.byName), ` ${changeAction(change)}`),
        change.readable
          ? h("a", { class: "path", href: `#/w/${encodeURIComponent(workspaceId)}/log?path=${encodeURIComponent(change.path)}` }, change.path)
          : h("span", { class: "path path-gone" }, `${change.path}（${change.op === "delete" ? "已删除" : "已不可读"}）`)),
      h("p", { class: "event-time" }, formatTime(change.at)))));
    toggle.textContent = expanded ? "收起" : `显示更早的 ${changes.length - CHANGES_SHOWN} 条`;
    toggle.setAttribute("aria-expanded", String(expanded));
  }
  toggle.addEventListener("click", () => {
    expanded = !expanded;
    draw();
  });
  draw();

  return h("section", { class: "panel changes-panel", "aria-label": "最近变更" },
    h("h2", null, "最近变更"),
    changes.length ? list : emptyState("还没有变更记录。", "成员在 OpenCode 中连接并写入后，变更会出现在这里。"),
    changes.length > CHANGES_SHOWN ? toggle : null);
}

function groupedTasks(tasks) {
  return h("div", { class: "task-groups" }, TASK_GROUPS.map((group) => {
    const items = tasks[group.status];
    return h("section", { class: "task-group", "aria-label": `${group.label}的团队任务` },
      h("h3", { class: "task-group-head" },
        h("span", { class: `dot dot-${group.tone}`, "aria-hidden": "true" }), group.label,
        h("span", { class: "count" }, String(items.length))),
      items.length ? h("ul", { class: "task-list" }, items.map(taskRow)) : h("p", { class: "group-empty" }, "暂无任务"));
  }));
}

export function overviewView(ctx, workspace) {
  const { api } = ctx;
  const body = h("div", { class: "stack" });

  function render(box, data) {
    const total = TASK_GROUPS.reduce((sum, group) => sum + data.tasks[group.status].length, 0);
    box.append(
      h("section", { class: "panel members-progress", "aria-label": "团队成员与进展" },
        h("h2", null, "团队成员与进展"),
        data.members.length ? h("ul", { class: "people" }, data.members.map(memberRow)) : h("p", { class: "quiet-line" }, "暂无成员进展。"),
        h("p", { class: "foot-note" }, "「最近活跃」是成员最近一次访问工作空间的时间，不代表设备在线或正在工作。")),
      h("section", { class: "panel team-tasks", "aria-label": "团队任务" },
        h("h2", { class: "h2-inline" }, "团队任务", tag("只读")),
        h("p", { class: "field-hint" }, "任务在 OpenCode 中声明、领取和更新，网页只展示当前状态。「待领取」只是状态标签，不是在这里领取的入口。"),
        total ? groupedTasks(data.tasks) : emptyState("这个空间还没有团队任务。", "团队任务在 OpenCode 中声明和领取。")),
      changesPanel(workspace.id, data.recentChanges));
  }

  return { el: body, start: loader(body, () => api.getOverview(workspace.id), render) };
}
