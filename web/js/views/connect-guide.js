import { copyButton, h } from "../dom.js";

// Placeholders only. The page never shows, stores or copies a real credential.
const EXAMPLE_COMMAND = [
  "# 先用安全的方式注入三个环境变量，不要把真实值写进命令历史或提示词：",
  "#   TEAM_SERVER_URL      <工作台地址>",
  "#   TEAM_SESSION_TOKEN   <你的账号会话>",
  "#   TEAM_TASK_KEY        <工作空间 key>",
  "node --experimental-strip-types <插件目录>/team/connect.ts <本地工作目录的绝对路径>",
].join("\n");

function step(title, ...body) {
  return h("li", { class: "guide-step" }, h("div", { class: "guide-step-body" }, h("p", { class: "guide-step-title" }, title), ...body));
}

/** The one connection guide, shown both from the overview and in "成员与接入". */
export function connectGuide(workspace) {
  return h("div", { class: "guide" },
    h("p", { class: "guide-lead" }, "在你自己的电脑上，通过命令行把本地目录连接到这个工作空间。网页不会代替你执行命令。"),
    h("ol", { class: "guide-steps" },
      step("准备三项信息", h("p", { class: "row-meta" }, "工作台地址、你的账号会话、工作空间 key（向负责人获取）。")),
      step("在本地目录运行连接命令",
        h("p", { class: "row-meta" }, "下面是带占位符的示例，不含任何真实凭据。"),
        h("div", { class: "codeblock" },
          h("div", { class: "codeblock-head" }, h("span", null, "命令示例"), copyButton(EXAMPLE_COMMAND, "示例命令")),
          h("pre", { class: "code", tabindex: "0", "aria-label": "连接命令示例" }, EXAMPLE_COMMAND))),
      step("在 OpenCode 中执行 /reload", h("p", { class: "row-meta" }, "之后每轮对话开始时会自动同步工程日志。"))),
    h("ul", { class: "guide-notes" },
      h("li", null, "连接只核对账号、成员资格和工作空间 key；不检查本地仓库或分支，也没有额外的确认步骤。"),
      h("li", null, "日常浏览这个网页不需要输入任何 key 或令牌。")),
    h("div", { class: "id-chip" }, h("span", { class: "row-meta" }, "本空间 ID"), h("code", null, workspace.id), copyButton(workspace.id, "空间 ID")));
}
