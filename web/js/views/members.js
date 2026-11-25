import { ROLE_LABELS, avatar, field, formatTime, h, loader, notify, runOnce, showFormError, tag } from "../dom.js";
import { connectGuide } from "./connect-guide.js";

const INVITE_RESULT = {
  invited: (email) => `已邀请 ${email}。对方用这个邮箱登录后，可以在「工作空间」页接受；接受之前不会成为成员。演示不会发送真实邮件。`,
  already_invited: (email) => `${email} 已经在邀请中，没有重复邀请。`,
  already_requested: (email) => `${email} 已经提交了加入申请，在「待审批申请」里通过即可，没有另外发出邀请。`,
};

const count = (n) => h("span", { class: "count" }, String(n));

export function membersView(ctx, workspace) {
  const { api } = ctx;
  const body = h("div", { class: "stack members-access" });
  let inviteNotice = ""; // Survives the reload that follows a successful invitation.
  let focusAfterReload = null;

  function requestsSection(data) {
    const requests = data.pendingRequests;
    if (!requests.length) return null;
    const heading = h("h3", { class: "h2-inline", tabindex: "-1", "data-focus": "requests" }, "待审批申请", count(requests.length));
    return h("section", { class: "access-requests", "aria-label": "待审批申请" }, heading,
      h("ul", { class: "callouts" }, requests.map((request) => {
        const approve = h("button", { type: "button", class: "btn btn-primary btn-small" }, h("span", { class: "btn-label" }, "通过"));
        const reject = h("button", { type: "button", class: "btn btn-small" }, h("span", { class: "btn-label" }, "拒绝"));
        const row = h("li", { class: "callout" },
          avatar(request.displayName, "lg"),
          h("div", { class: "request-identity" },
            h("p", { class: "callout-title" }, `${request.displayName} 申请加入`),
            h("p", { class: "row-meta" }, `${request.email} · 申请于 ${formatTime(request.at)}`)),
          h("div", { class: "actions" }, approve, reject));
        const decide = async (button, other, approved) => {
          row.querySelector(".row-error")?.remove();
          try {
            await runOnce(button, () => api.decideMembership(workspace.id, request.accountId, approved), [other]);
            notify(approved ? `已通过 ${request.displayName} 的申请。` : `已拒绝 ${request.displayName} 的申请，对方仍不能进入空间。`);
            focusAfterReload = "requests";
            reload();
          } catch (error) {
            row.append(h("p", { class: "row-error", role: "alert" }, `${error.message}申请仍是待审批，可以重试。`));
          }
        };
        approve.addEventListener("click", () => decide(approve, reject, true));
        reject.addEventListener("click", () => decide(reject, approve, false));
        return row;
      })));
  }

  function membersSection(data) {
    return h("section", { class: "access-roster", "aria-label": "已加入的成员" },
      h("ul", { class: "access-members" }, data.members.map((member) => h("li", { class: "access-member" },
        h("div", { class: "access-identity" }, avatar(member.displayName, "md"),
          h("div", { class: "access-person" }, h("p", { class: "access-name" }, member.displayName), h("p", { class: "row-meta" }, member.email))),
        h("div", { class: "access-role" }, tag(ROLE_LABELS[member.role], member.role === "owner" ? "accent" : "neutral")),
        h("p", { class: "access-activity" }, h("span", null, "最近活跃"), formatTime(member.lastSeenAt))))),
      !data.members.length ? h("p", { class: "quiet-line" }, "暂无成员。") : null,
      data.role === "owner" ? null : h("p", { class: "field-hint" }, "邀请成员和审批加入申请由负责人处理。"));
  }

  function inviteSection(data) {
    const email = field({ label: "被邀请人的邮箱", type: "email", name: "email", spellcheck: "false", autocomplete: "off",
      hint: "演示可邀请：xu.an@example.test、chen.mo@example.test。", "data-focus": "invite" });
    const formMessage = h("p", { class: "form-error", role: "alert" });
    const result = h("p", { class: "form-ok", role: "status" }, inviteNotice);
    const submit = h("button", { type: "submit", class: "btn btn-primary" }, "邀请成员");
    email.row.classList.add("field-inline");
    email.row.append(submit);

    async function onSubmit(event) {
      event.preventDefault();
      email.setError("");
      formMessage.textContent = "";
      result.textContent = "";
      try {
        const reply = await runOnce(submit, () => api.inviteMember(workspace.id, email.input.value), [email.input]);
        inviteNotice = INVITE_RESULT[reply.status](reply.email);
        focusAfterReload = "invite";
        reload();
      } catch (error) {
        if (error.code === "conflict") {
          email.setError(error.message);
          email.input.focus();
        } else {
          showFormError(error, { email }, formMessage);
          if (error.code === "unavailable") formMessage.textContent = `${error.message}可以直接再提交一次。`;
        }
      }
    }

    return h("section", { class: "access-invite", "aria-label": "邀请成员" },
      h("div", { class: "access-invite-intro" }, h("h3", null, "邀请成员"),
        h("p", { class: "row-meta" }, "对方接受邀请后，才会加入空间。")),
      h("div", { class: "access-invite-body" },
      h("form", { class: "stack-sm", novalidate: true, onsubmit: onSubmit }, email.row, formMessage, result),
      data.invitations.length
        ? h("div", { class: "subsection" },
            h("h3", { class: "h2-inline" }, "等待对方接受的邀请", count(data.invitations.length)),
            h("ul", { class: "rows" }, data.invitations.map((invitation) => h("li", { class: "row" },
              h("div", { class: "row-main" }, h("span", { class: "row-title" }, invitation.email), tag("已邀请", "pending")),
              h("p", { class: "row-meta" }, `${invitation.invitedByName} 邀请于 ${formatTime(invitation.at)} · 尚未接受，还不是成员`)))))
        : h("p", { class: "quiet-line" }, "没有等待接受的邀请。")));
  }

  function guidePanel() {
    return h("section", { class: "panel access-connection", "aria-label": "连接 OpenCode" },
      h("h2", null, "连接 OpenCode"), connectGuide(workspace), reposPanel());
  }

  function reposPanel() {
    return h("details", { class: "access-repos" },
      h("summary", null, "参考仓库", h("span", { class: "row-meta" }, "仅供浏览，不参与接入")),
      h("div", { class: "access-repos-body" },
      workspace.links.length
        ? h("ul", { class: "plain-list" }, workspace.links.map((link) => h("li", null, h("code", { class: "chip" }, link))))
        : h("p", { class: "empty-hint" }, "创建时没有填写参考仓库链接。"),
      h("p", { class: "field-hint" }, "仓库链接只供浏览，不参与接入。")));
  }

  const reload = loader(body, () => api.getMembers(workspace.id), (box, data) => {
    const owner = data.role === "owner";
    box.append(
      h("section", { class: "panel access-management", "aria-label": "成员管理" },
        h("header", { class: "access-heading" }, h("h2", { class: "h2-inline" }, "成员", count(data.members.length)),
          owner && !data.pendingRequests.length
            ? h("p", { class: "quiet-line", tabindex: "-1", "data-focus": "requests" }, "没有待审批的申请。") : null),
        owner ? requestsSection(data) : null, membersSection(data), owner ? inviteSection(data) : null),
      guidePanel());
    if (focusAfterReload) box.querySelector(`[data-focus="${focusAfterReload}"]`)?.focus();
    focusAfterReload = null;
  });

  return { el: body, start: reload };
}
