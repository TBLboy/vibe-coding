import { h, notify, openDialog, runOnce } from "../dom.js";

const FAULTS = [
  { kind: "read", label: "让下一次读取失败", armed: "已设置：下一次读取会失败一次" },
  { kind: "submit", label: "让下一次提交失败", armed: "已设置：下一次提交会失败一次" },
];

/** Demo-only controls. None of this is a product feature. */
export function openDemoTools(ctx, trigger) {
  const { api } = ctx;
  openDialog({
    title: "演示工具",
    trigger,
    build(body, { close }) {
      const identities = h("div", { class: "stack-sm" });
      const faults = h("div", { class: "stack-sm" });
      const resetBox = h("div", { class: "actions" });

      api.listDemoAccounts().then(({ accounts }) => {
        identities.replaceChildren(...accounts.map((account) => {
          const current = account.id === ctx.session.account.id;
          const button = h("button", { type: "button", class: "btn btn-block", disabled: current },
            h("span", { class: "btn-label" }, current ? `${account.displayName}（当前身份）` : `切换为${account.displayName}`));
          button.addEventListener("click", async () => {
            try {
              await runOnce(button, () => api.loginDemo(account.id));
              close();
              notify(`已切换为${account.displayName}，演示数据保持不变。`);
              ctx.sessionChanged("#/workspaces");
            } catch (error) {
              notify(error.message, "error");
            }
          });
          return h("div", { class: "demo-row" }, button, h("p", { class: "field-hint" }, account.note));
        }));
      });

      function renderFaults(state) {
        faults.replaceChildren(...FAULTS.map((fault) => {
          const armed = state[fault.kind];
          const button = h("button", { type: "button", class: "btn", "aria-pressed": String(armed) }, armed ? "取消" : fault.label);
          button.addEventListener("click", async () => renderFaults(await api.demo.setFault(fault.kind, !armed)));
          return h("div", { class: "demo-row" }, button, h("p", { class: "field-hint", role: "status" }, armed ? fault.armed : "未设置"));
        }));
      }
      api.demo.getFaults().then(renderFaults);

      function renderReset(confirming) {
        if (!confirming) {
          const ask = h("button", { type: "button", class: "btn" }, "恢复种子数据");
          ask.addEventListener("click", () => {
            renderReset(true);
            resetBox.querySelector("button").focus();
          });
          resetBox.replaceChildren(ask);
          return;
        }
        const confirm = h("button", { type: "button", class: "btn btn-danger" }, "确认恢复");
        const cancel = h("button", { type: "button", class: "btn" }, "取消");
        confirm.addEventListener("click", async () => {
          await runOnce(confirm, () => api.demo.reset(), [cancel]);
          close();
          notify("已恢复为初始演示数据。");
          ctx.sessionChanged("#/workspaces");
        });
        cancel.addEventListener("click", () => {
          renderReset(false);
          resetBox.querySelector("button").focus();
        });
        resetBox.replaceChildren(confirm, cancel);
      }
      renderReset(false);

      body.append(
        h("p", { class: "field-hint" }, "这些入口只为体验原型而存在，不属于产品功能。所有身份共用同一份本机演示数据。"),
        h("h3", null, "切换演示身份"), identities,
        h("h3", null, "模拟一次失败"),
        h("p", { class: "field-hint" }, "设置后关闭本窗口，再执行一次读取（打开页面）或提交（创建、邀请、申请、审批），即可看到失败与重试。"),
        faults,
        h("h3", null, "演示数据"),
        h("p", { class: "field-hint" }, "恢复后，你在演示中创建的空间、邀请和申请都会被清除。"),
        resetBox);
    },
  });
}
