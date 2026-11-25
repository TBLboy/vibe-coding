import { field, h, notify, runOnce, showFormError, tag } from "../dom.js";

const PRIMARY = { owner: "使用负责人演示账号", member: "使用成员演示账号" };

export function loginView(ctx) {
  const { api } = ctx;
  const email = field({ label: "邮箱", type: "email", name: "email", autocomplete: "username", spellcheck: "false" });
  const password = field({ label: "密码", type: "password", name: "password", autocomplete: "off" });
  const formMessage = h("p", { class: "form-error", role: "alert" });
  const submit = h("button", { type: "submit", class: "btn btn-primary" }, "登录");

  async function onSubmit(event) {
    event.preventDefault();
    email.setError("");
    password.setError("");
    formMessage.textContent = "";
    try {
      await runOnce(submit, () => api.login({ email: email.input.value, password: password.input.value }));
      ctx.sessionChanged();
    } catch (error) {
      showFormError(error, { email, password }, formMessage);
      if (error.code === "login_mismatch") {
        formMessage.textContent = "邮箱或密码不匹配。请检查后重试，或直接使用下方的演示账号。";
        password.input.value = "";
        password.input.focus();
      }
    }
  }

  const demoList = h("div", { class: "stack-sm" }, h("p", { class: "loading", role: "status" }, "正在加载演示账号…"));
  const demoHint = h("p", { class: "field-hint" });

  async function useDemo(button, accountId) {
    try {
      await runOnce(button, () => api.loginDemo(accountId), [...demoList.querySelectorAll("button")]);
      ctx.sessionChanged();
    } catch (error) {
      notify(error.message, "error");
    }
  }

  function demoButton(account, label, primary) {
    const button = h("button", { type: "button", class: primary ? "btn btn-block" : "btn btn-block btn-small" },
      h("span", { class: "btn-label" }, label));
    button.addEventListener("click", () => useDemo(button, account.id));
    return h("div", { class: "demo-row" }, button, h("p", { class: "field-hint" }, `${account.displayName} · ${account.note}`));
  }

  api.listDemoAccounts().then(({ accounts, password: demoPassword }) => {
    const primary = accounts.filter((account) => PRIMARY[account.kind]);
    const others = accounts.filter((account) => !PRIMARY[account.kind]);
    demoList.replaceChildren(
      h("div", { class: "demo-grid" }, ...primary.map((account) => demoButton(account, PRIMARY[account.kind], true))),
      ...(others.length ? [h("p", { class: "demo-more" }, "其他演示账号"), h("div", { class: "demo-grid" }, ...others.map((account) => demoButton(account, `以${account.displayName}登录`, false)))] : []),
    );
    demoHint.textContent = `也可以在上方表单输入任一演示邮箱和演示密码 ${demoPassword}。请不要输入任何真实密码。`;
  });

  const el = h("div", { class: "login" },
    h("div", { class: "panel login-card" },
      h("div", { class: "login-brand" }, h("span", { class: "brand-mark brand-mark-lg", "aria-hidden": "true" }, "团"), h("span", { class: "wordmark" }, "团队工作台")),
      h("div", { class: "stack-sm" }, h("h1", { tabindex: "-1" }, "登录"), h("p", { class: "login-lead" }, "登录后进入你的团队工作空间。")),
      h("form", { class: "stack", novalidate: true, onsubmit: onSubmit }, email.row, password.row, formMessage, submit),
      h("section", { class: "demo-box", "aria-label": "演示模式" },
        h("h2", null, tag("演示模式", "demo"), " 不需要任何真实凭据"),
        h("p", { class: "field-hint" }, "所有账号和数据都是虚构的，只保存在这个浏览器里。"),
        demoList,
        demoHint)));

  return { el };
}
