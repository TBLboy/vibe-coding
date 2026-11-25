import {
  ROLE_LABELS, avatar, copyButton, emptyState, field, formatTime, h, icon, loader, notify, openDialog, runOnce, showFormError, tag,
} from "../dom.js";

const APPLICATION_TEXT = {
  requested: "等待负责人审批。通过之前不能进入这个空间。",
  rejected: "负责人没有通过这次申请，你不能进入这个空间。需要时可以联系负责人，或重新申请。",
};

/** Inline failure next to the control that caused it; the control stays available for a retry. */
function rowError(row, error) {
  row.querySelector(".row-error")?.remove();
  row.append(h("p", { class: "row-error", role: "alert" }, `${error.message}可以重试。`));
}

export function workspacesView(ctx) {
  const { api } = ctx;
  const body = h("div", { class: "stack" });
  const createButton = h("button", { type: "button", class: "btn btn-primary" }, icon("plus"), h("span", { class: "btn-label" }, "创建工作空间"));
  const applyButton = h("button", { type: "button", class: "btn" }, "申请加入");

  function render(box, data) {
    const count = (n) => h("span", { class: "count" }, String(n));

    const invitations = data.invitations.map((item) => {
      const accept = h("button", { type: "button", class: "btn btn-primary btn-small" }, h("span", { class: "btn-label" }, "接受邀请"));
      const row = h("li", { class: "callout" },
        avatar(item.workspaceName, "lg"),
        h("div", null,
          h("p", { class: "callout-title" }, `${item.invitedByName} 邀请你加入「${item.workspaceName}」`),
          h("p", { class: "row-meta" }, `${formatTime(item.at)} · 接受之前还不能进入这个空间`)),
        accept);
      accept.addEventListener("click", async () => {
        try {
          await runOnce(accept, () => api.acceptInvitation(item.workspaceId));
          notify(`已加入「${item.workspaceName}」。`);
          await reload();
          ctx.focusHeading();
        } catch (error) {
          rowError(row, error);
        }
      });
      return row;
    });

    const joined = data.joined.length
      ? h("div", { class: "ws-grid" }, data.joined.map((item) =>
          h("a", { class: "ws-card", href: `#/w/${encodeURIComponent(item.id)}/overview` },
            h("div", { class: "ws-card-top" }, avatar(item.name, "lg"), tag(ROLE_LABELS[item.role], item.role === "owner" ? "accent" : "neutral")),
            h("p", { class: "ws-name" }, item.name),
            h("p", { class: "row-meta" }, `${item.memberCount} 位成员`),
            h("div", { class: "ws-foot" }, h("code", { class: "ws-id" }, item.id), h("span", { class: "ws-enter" }, "进入")))))
      : emptyState("你还没有加入任何工作空间。", "创建一个新空间，或向负责人要到空间 ID 后申请加入。");

    const applications = data.applications.map((item) => {
      const rejected = item.status === "rejected";
      const again = rejected ? h("button", { type: "button", class: "btn btn-small" }, h("span", { class: "btn-label" }, "重新申请")) : null;
      const row = h("li", { class: "row" },
        h("div", { class: "row-main" },
          h("span", { class: "row-title" }, item.workspaceName),
          tag(rejected ? "未通过" : "待审批", rejected ? "error" : "pending"),
          again ? h("span", { class: "row-aside" }, again) : null),
        h("p", { class: "row-meta" }, `ID ${item.workspaceId} · ${APPLICATION_TEXT[item.status]}`));
      again?.addEventListener("click", async () => {
        try {
          await runOnce(again, () => api.requestMembership(item.workspaceId));
          notify("已重新提交申请，等待负责人审批。");
          await reload();
          ctx.focusHeading();
        } catch (error) {
          rowError(row, error);
        }
      });
      return row;
    });

    const quiet = data.joined.length && !data.invitations.length && !data.applications.length;
    box.append(...[
      invitations.length ? h("section", { class: "block", "aria-label": "待你处理的邀请" },
        h("h2", { class: "section-title" }, "待你处理", count(invitations.length)),
        h("ul", { class: "callouts" }, invitations)) : null,
      h("section", { class: "block", "aria-label": "已加入的工作空间" },
        h("h2", { class: "section-title" }, "已加入", count(data.joined.length)), joined),
      applications.length ? h("section", { class: "block", "aria-label": "我的申请" },
        h("h2", { class: "section-title" }, "我的申请", count(applications.length)),
        h("ul", { class: "rows panel" }, applications)) : null,
      quiet ? h("p", { class: "quiet-line" }, "没有待处理的邀请，也没有进行中的申请。") : null,
    ].filter(Boolean));
  }

  const reload = loader(body, () => api.listMyWorkspaces(), render);
  createButton.addEventListener("click", () => openCreateDialog(ctx, createButton, reload));
  applyButton.addEventListener("click", () => openApplyDialog(ctx, applyButton, reload));

  const el = h("div", { class: "page" },
    h("div", { class: "page-head" },
      h("div", { class: "page-title" }, h("h1", { tabindex: "-1" }, "工作空间"), h("p", { class: "page-sub" }, "你加入的团队空间，以及需要你处理的邀请和申请。")),
      h("div", { class: "actions" }, createButton, applyButton)),
    body);
  return { el, start: reload };
}

function openCreateDialog(ctx, trigger, onChanged) {
  openDialog({
    title: "创建工作空间",
    trigger,
    build(body, { close }) {
      const name = field({ label: "空间名称", name: "name", maxlength: "100", required: true, autocomplete: "off" });
      const links = []; // { row, input, setError }
      const linkList = h("div", { class: "stack-sm" });
      const formMessage = h("p", { class: "form-error", role: "alert" });
      const submit = h("button", { type: "submit", class: "btn btn-primary" }, "创建");
      const addLink = h("button", { type: "button", class: "btn btn-small" }, icon("plus"), h("span", { class: "btn-label" }, "添加一个链接"));

      function addLinkRow() {
        const entry = field({ label: `仓库链接 ${links.length + 1}`, name: "link", type: "text", spellcheck: "false", autocomplete: "off", placeholder: "https://git.example.test/team/repo.git" });
        const remove = h("button", { type: "button", class: "btn btn-small btn-quiet" }, "移除");
        remove.addEventListener("click", () => {
          links.splice(links.indexOf(entry), 1);
          entry.row.remove();
          links.forEach((item, index) => { item.row.querySelector("label").textContent = `仓库链接 ${index + 1}`; });
          addLink.focus();
        });
        entry.row.append(remove);
        links.push(entry);
        linkList.append(entry.row);
        return entry;
      }
      addLink.addEventListener("click", () => addLinkRow().input.focus());
      addLinkRow();

      async function onSubmit(event) {
        event.preventDefault();
        name.setError("");
        links.forEach((item) => item.setError(""));
        formMessage.textContent = "";
        try {
          const controls = [addLink, ...body.querySelectorAll("input, button")];
          const result = await runOnce(submit, () => ctx.api.createWorkspace({ name: name.input.value, links: links.map((item) => item.input.value) }), controls);
          onChanged();
          showCreated(result);
        } catch (error) {
          const targets = { name, links: links[0] };
          links.forEach((item, index) => { targets[`links.${index}`] = item; });
          showFormError(error, targets, formMessage);
          if (error.code === "unavailable") formMessage.textContent = `${error.message}可以直接再提交一次。`;
        }
      }

      function showCreated({ workspace, demoKey }) {
        const heading = h("p", { class: "notice-title", tabindex: "-1" }, `已创建「${workspace.name}」，你是这个空间的负责人。`);
        body.replaceChildren(
          h("div", { class: "notice notice-ok", role: "status" }, heading),
          h("dl", { class: "facts" },
            h("dt", null, "工作空间 ID"),
            h("dd", null, h("code", null, workspace.id), copyButton(workspace.id, "空间 ID"),
              h("p", { class: "field-hint" }, "把它告诉同事，对方登录后可以用它申请加入。")),
            h("dt", null, "示例 key"),
            h("dd", null, h("code", null, demoKey), tag("演示 · 不可用", "error"),
              h("p", { class: "field-hint" }, "真实环境里 key 用于在本地连接 OpenCode。这里只是占位文字，不能用于任何连接。"))),
          h("div", { class: "actions" },
            h("a", { class: "btn btn-primary", href: `#/w/${encodeURIComponent(workspace.id)}/overview`, onclick: close }, "进入空间"),
            h("button", { type: "button", class: "btn", onclick: close }, "完成")));
        heading.focus();
      }

      body.append(h("form", { class: "stack", novalidate: true, onsubmit: onSubmit },
        name.row,
        h("fieldset", { class: "fieldset" },
          h("legend", null, "参考仓库链接（可选）"),
          h("p", { class: "field-hint" }, "只给成员浏览，不参与接入，也不需要填写分支。"),
          linkList,
          addLink),
        formMessage,
        h("div", { class: "actions" }, submit, h("button", { type: "button", class: "btn", onclick: close }, "取消"))));
      name.input.focus();
    },
  });
}

const APPLY_RESULT = {
  requested: (r) => (r.existing
    ? `你已经申请过「${r.workspaceName}」，仍在等待审批，没有重复提交。`
    : `已向「${r.workspaceName}」提交申请，等待负责人审批。`),
  invited: (r) => `你已经收到「${r.workspaceName}」的邀请，在「待处理邀请」里直接接受即可，不需要再申请。`,
  active: (r) => `你已经是「${r.workspaceName}」的成员，可以直接进入。`,
};

function openApplyDialog(ctx, trigger, onChanged) {
  openDialog({
    title: "申请加入工作空间",
    trigger,
    build(body, { close }) {
      const id = field({ label: "工作空间 ID", name: "workspaceId", spellcheck: "false", autocomplete: "off", hint: "向空间负责人索取，形如 ws_demo_pay。" });
      const formMessage = h("p", { class: "form-error", role: "alert" });
      const result = h("p", { class: "form-ok", role: "status" });
      const submit = h("button", { type: "submit", class: "btn btn-primary" }, "提交申请");

      async function onSubmit(event) {
        event.preventDefault();
        id.setError("");
        formMessage.textContent = "";
        result.textContent = "";
        try {
          const reply = await runOnce(submit, () => ctx.api.requestMembership(id.input.value), [id.input]);
          result.textContent = APPLY_RESULT[reply.status](reply);
          onChanged();
        } catch (error) {
          if (error.code === "not_found") {
            id.setError(error.message);
            id.input.focus();
          } else {
            showFormError(error, { workspaceId: id }, formMessage);
            if (error.code === "unavailable") formMessage.textContent = `${error.message}可以直接再提交一次。`;
          }
        }
      }

      body.append(h("form", { class: "stack", novalidate: true, onsubmit: onSubmit },
        id.row, formMessage, result,
        h("div", { class: "actions" }, submit, h("button", { type: "button", class: "btn", onclick: close }, "关闭"))));
      id.input.focus();
    },
  });
}

/** Deep link for one invitation. It shows nothing about the workspace unless the invitation is for this account. */
export function invitationView(ctx, route) {
  const { api } = ctx;
  const body = h("div", { class: "stack" });
  const back = h("a", { class: "btn", href: "#/workspaces" }, icon("back"), h("span", { class: "btn-label" }, "返回工作空间列表"));

  const reload = loader(body, () => api.getInvitation(route.workspaceId), (box, invitation) => {
    const accept = h("button", { type: "button", class: "btn btn-primary" }, "接受邀请");
    const panel = h("section", { class: "panel" },
      h("h2", null, invitation.workspaceName),
      h("p", null, `${invitation.invitedByName} 邀请你加入 · ${formatTime(invitation.at)}。接受后即可查看概览和工程日志。`),
      h("div", { class: "actions" }, accept, back));
    accept.addEventListener("click", async () => {
      try {
        await runOnce(accept, () => api.acceptInvitation(route.workspaceId));
        notify(`已加入「${invitation.workspaceName}」。`);
        ctx.go(`#/w/${encodeURIComponent(route.workspaceId)}/overview`);
      } catch (error) {
        rowError(panel, error);
      }
    });
    box.append(panel);
  }, {
    renderError: (error) => (error.code === "invitation_not_found"
      ? h("section", { class: "panel" },
          h("h2", null, "这条邀请不属于当前账号"),
          h("p", null, `当前登录的是 ${ctx.session.account.email}。邀请只对被邀请的邮箱有效，也可能已经被接受。`),
          h("p", null, "下一步：请负责人邀请你登录用的邮箱，或回到列表用空间 ID 申请加入。"),
          h("div", { class: "actions" }, back))
      : null),
  });

  const el = h("div", { class: "page" }, h("div", { class: "page-head" }, h("h1", { tabindex: "-1" }, "加入邀请")), body);
  return { el, start: reload };
}
