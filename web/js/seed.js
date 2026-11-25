// Synthetic demo data only. Every name is invented and every address uses the
// reserved example.test domain. Nothing here is a real credential or endpoint.

export const DEMO_PASSWORD = "demo-only";
export const DEMO_KEY_PLACEHOLDER = "demo-key-not-usable";
export const SEED_WORKSPACE_ID = "ws_demo_pay";

const MIN = 60 * 1000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

const ACCOUNTS = [
  { id: "acct_zhou", email: "zhou.ning@example.test", displayName: "周宁", kind: "owner", note: "「支付项目」负责人" },
  { id: "acct_lin", email: "lin.zhou@example.test", displayName: "林舟", kind: "member", note: "「支付项目」成员" },
  { id: "acct_chen", email: "chen.mo@example.test", displayName: "陈默", kind: "applicant", note: "尚未加入，可体验申请加入" },
  { id: "acct_xu", email: "xu.an@example.test", displayName: "许安", kind: "invitee", note: "尚未加入，可体验接受邀请" },
];

const TEAM_RULES = `# 支付项目团队规范

本文件对所有成员和他们的 Agent 生效。

## 协作约定

- 开始开发前先阅读相关规格，再声明或领取团队任务。
- 一个任务只由一名成员持有；范围重叠时先沟通再动手。
- 进度写在自己的成员进度文件里，不改他人的记录。

## 代码约定

- 金额一律使用整数分，不使用浮点数。
- 回调处理必须幂等，重复通知不得重复入账。
- 密钥、令牌不写入代码仓库和工程日志。
`;

const REVIEW_CHECKLIST = `# 合并前自查清单

1. 改动对应一个团队任务，范围与声明一致。
2. 相关规格已补充或更新。
3. 超时、重复通知、验签失败等异常路径有测试。
4. 日志里不含密钥和完整卡号。
`;

const API_CONVENTIONS = `# 接口约定

## 错误响应

所有接口返回统一结构：

\`\`\`json
{ "code": "invalid_request", "message": "金额必须为正整数" }
\`\`\`

## 输出转义

回调结果页不得原样输出第三方字段。下面两行只是示例文本，在本页中不会被执行：

<script>alert("这是一段不会执行的示例")</script>
<img src="x" onerror="alert(1)">
`;

const SPEC_CALLBACK = `# 支付回调模块

## 目标

接收支付通道的异步通知，验签后更新订单状态。

## 规则

- 验签失败返回 401，不落库。
- 同一通知编号重复到达时返回成功，但只处理一次。
- 订单已是终态时忽略后续通知，并记录一条活动。

## 接口

POST /payment/callback/{channel}

## 未决

- 通道 B 的通知重试间隔仍待对方确认。
`;

const SPEC_REFUND = `# 退款模块

## 规则

- 退款金额不得超过已支付金额减去已退款金额。
- 同一退款请求号重复提交时返回首次结果。

## 状态

处理中 → 成功 / 失败。失败后可重新发起，需使用新的退款请求号。
`;

const PROGRESS_LIN = `# 林舟的进度

## 今天

- 完成回调验签与通道 A 的联调，重复通知场景已通过。
- 通道 B 沙箱返回字段与规格不一致，已在规格「未决」中补充。

## 接下来

- 等通道 B 确认重试间隔后补充超时用例。
`;

const PROGRESS_ZHOU = `# 周宁的进度

## 本周

- 梳理对账任务调度方案，确定按通道分批。
- 评审支付回调模块规格第 2 版。
`;

/** Build a fresh demo state. Timestamps are relative to `now` so the data always looks recent. */
export function createSeed(now) {
  const ws = SEED_WORKSPACE_ID;
  const at = (ago) => now - ago;

  const tasks = [
    { id: "task_pay_callback", title: "支付回调联调", status: "claimed", claimedBy: "acct_lin", scope: ["src/payment/callback/"], createdBy: "acct_zhou", updatedAt: at(52 * MIN) },
    { id: "task_reconcile", title: "对账任务调度", status: "claimed", claimedBy: "acct_zhou", scope: ["src/reconcile/"], createdBy: "acct_zhou", updatedAt: at(3 * HOUR) },
    { id: "task_refund_idem", title: "退款接口幂等校验", status: "open", claimedBy: null, scope: ["src/payment/refund/"], createdBy: "acct_zhou", updatedAt: at(DAY) },
    { id: "task_callback_tests", title: "补充回调验签单元测试", status: "open", claimedBy: null, scope: ["tests/payment/callback/"], createdBy: "acct_lin", updatedAt: at(20 * HOUR) },
    { id: "task_order_api", title: "支付下单接口", status: "done", claimedBy: "acct_lin", scope: ["src/payment/order/"], createdBy: "acct_zhou", updatedAt: at(2 * DAY) },
    { id: "task_legacy_gateway", title: "旧网关适配", status: "abandoned", claimedBy: null, scope: ["src/gateway/legacy/"], createdBy: "acct_zhou", reason: "旧网关下线，改走新通道。", updatedAt: at(19 * HOUR) },
  ].map((task) => ({ workspaceId: ws, ...task }));

  const taskFile = (task) => JSON.stringify({
    id: task.id, title: task.title, status: task.status, claimedBy: task.claimedBy,
    scope: task.scope, ...(task.reason ? { reason: task.reason } : {}),
  }, null, 2);

  // Ordered history. A later entry for the same path supersedes the earlier one.
  const history = [
    { path: "constitution/AGENTS.md", by: "acct_zhou", ago: 3 * DAY, content: TEAM_RULES },
    { path: "constitution/review-checklist.md", by: "acct_zhou", ago: 3 * DAY - HOUR, content: REVIEW_CHECKLIST },
    { path: "specs/api-conventions.md", by: "acct_zhou", ago: 2 * DAY + 5 * HOUR, content: API_CONVENTIONS },
    { path: "specs/modules/legacy-gateway.md", by: "acct_zhou", ago: 2 * DAY + 4 * HOUR, content: "# 旧网关适配\n" },
    { path: "specs/modules/refund.md", by: "acct_zhou", ago: 2 * DAY + 3 * HOUR, content: SPEC_REFUND },
    { path: "specs/modules/payment-callback.md", by: "acct_zhou", ago: 2 * DAY + 2 * HOUR, content: SPEC_CALLBACK },
    { path: "work/task_order_api.json", by: "acct_lin", ago: 2 * DAY, content: taskFile(tasks[4]) },
    { path: "work/task_refund_idem.json", by: "acct_zhou", ago: DAY, content: taskFile(tasks[2]) },
    { path: "members/acct_lin/progress.md", by: "acct_lin", ago: 23 * HOUR, content: PROGRESS_LIN },
    { path: "work/task_callback_tests.json", by: "acct_lin", ago: 20 * HOUR, content: taskFile(tasks[3]) },
    { path: "specs/modules/legacy-gateway.md", by: "acct_zhou", ago: 19 * HOUR + 10 * MIN, deleted: true },
    { path: "work/task_legacy_gateway.json", by: "acct_zhou", ago: 19 * HOUR, content: taskFile(tasks[5]) },
    { path: "members/acct_zhou/progress.md", by: "acct_zhou", ago: 4 * HOUR, content: PROGRESS_ZHOU },
    { path: "work/task_reconcile.json", by: "acct_zhou", ago: 3 * HOUR, content: taskFile(tasks[1]) },
    { path: "work/task_pay_callback.json", by: "acct_lin", ago: 52 * MIN, content: taskFile(tasks[0]) },
    { path: "specs/modules/payment-callback.md", by: "acct_zhou", ago: 34 * MIN, content: SPEC_CALLBACK },
    { path: "members/acct_lin/progress.md", by: "acct_lin", ago: 8 * MIN, content: PROGRESS_LIN },
  ];

  const documents = new Map();
  const versions = new Map();
  const changes = history.map((entry, index) => {
    const version = (versions.get(entry.path) ?? 0) + 1;
    versions.set(entry.path, version);
    if (entry.deleted) documents.delete(entry.path);
    else documents.set(entry.path, { workspaceId: ws, path: entry.path, content: entry.content, version, updatedAt: at(entry.ago), updatedBy: entry.by });
    return { workspaceId: ws, seq: index + 1, path: entry.path, op: entry.deleted ? "delete" : "upsert", version, by: entry.by, at: at(entry.ago) };
  });

  return {
    schemaVersion: 1,
    sessionAccountId: null,
    faults: { read: false, submit: false },
    counter: 0,
    accounts: ACCOUNTS.map((account) => ({ ...account })),
    workspaces: [
      {
        id: ws, name: "支付项目", ownerId: "acct_zhou", createdAt: at(3 * DAY),
        links: ["https://git.example.test/pay/pay-core.git", "git@git.example.test:pay/pay-web.git"],
      },
    ],
    memberships: [
      { workspaceId: ws, accountId: "acct_zhou", role: "owner", status: "active", at: at(3 * DAY), decidedAt: at(3 * DAY), lastSeenAt: at(2 * MIN) },
      { workspaceId: ws, accountId: "acct_lin", role: "member", status: "active", at: at(3 * DAY - HOUR), decidedAt: at(3 * DAY - HOUR), lastSeenAt: at(6 * MIN) },
    ],
    invitations: [],
    tasks,
    documents: [...documents.values()],
    changes,
  };
}
