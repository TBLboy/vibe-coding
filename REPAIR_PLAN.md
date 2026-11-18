# Vibe Coding V2 — P0/P1 修复计划与交付说明

基线：用户上传的 `vibe-coding.zip`，原仓库 HEAD `9d023b3`。本交付是源码修复候选版，不是已经通过真实 OpenCode 宿主验收的正式发布。未修改原 ZIP、未推送远程、未操作用户实际 OpenCode 配置。

## 1. 目标与实施顺序

原则：保留单主 Agent、单独只读 Reviewer、三模式和轻量 Task/Project Memory，不增加独立数据库、额外 Agent 或全套工作流。先保障系统不变量和外部副作用，再改善验证体系，最后深化工程方法论。

| 顺序 | 优先级 | 任务 | 状态 |
|---|---|---|---|
| 1 | P0 | Runtime 真实执行 Task 状态转换，防直接篡改 | 已实现、本地回归通过 |
| 2 | P0 | 冻结策略跨 Session 持久化，绑定所有权 | 已实现、本地回归通过 |
| 3 | P0 | Reviewer 许可与实际完成分离、绑定审查轮次 | 已实现、模拟宿主回归通过；真实宿主待验收 |
| 4 | P0 | 验证绑定实际产物，过期证据阻止关闭 | 已实现、本地回归通过 |
| 5 | P0 | Installer 所有权与安全更新；Archive 限制 Git 发布和秘密泄漏 | 已实现、本地隔离实验通过；真实用户配置未操作 |
| 6 | P1 | Mode/Risk/Task/Skill 边界与操作契约 | 已同步；真实 Agent 遵循情况待测 |
| 7 | P1 | L1/L2 测试覆盖生产入口、错误路径；修复 worktree 与安装契约缺失 | 已实现、本地回归通过 |
| 8 | P1 | L3/L4 Agent/Skill 行为评估 | 已有 8 个案例规格、独立评分脚本及其测试；真实模型执行、可重放仓库夹具及宿主验收待完成 |
| 9 | P2 | 深化 architecture-decision、engineering-landing、verification 的工程思维模型 | 未实施 |
| 10 | P3 | 深化 onboarding、research、spec、decompose；统一重复决策规则、解决 explicit-only 路由、分支审查模拟合并等问题 | 未实施 |

## 2. 关键设计与实现

### Runtime

- `runtime/core/task-machine.ts`：生命周期转换、阻塞恢复、证据失效、决策记录；拒绝越级及非法终态。
- `runtime/opencode/plugins/vibe-v2/task-control.ts`：新 Task 只能从 fresh prepare 注册；Runtime 持有后续写入权。原 Task JSON 仍是可读的业务状态；插件存储额外保存项目级小型 receipt（owner、policy、digest、closed、pending review call），没有复制 Task 的业务内容。跨 Session 恢复转交所有权，不改变冻结策略。
- `runtime/opencode/plugins/vibe-v2/setup.ts`：原生产入口调用的实际适配层，权限许可只登记 native call identity，真实 `tool.execute.after` 完成才处理 Reviewer JSON；必须匹配新前台子 Session、父 Session、Agent、调用 ID 与当前产物。失败、伪造、陈旧结果不完成 Task。
- `runtime/core/artifact-evidence.ts`：验证开始时记录显式文件、Git HEAD、改动的 tracked/untracked 文件的 SHA-256 指纹（含路径、内容及模式）；验证结果提交、review 授权/完成及 close 检查新鲜度。对符号链接及越界路径拒绝处理。验证期间或验证后发生变化，重新验证。
- `docs/03-STATE-MACHINE.md`：完整工具调用契约。Main 与 Reviewer 的操作提示、核心 Skill 的公共规则和数据契约同步。

### Installer / Archive

- `scripts/vibe_v2_installer.py`：安装前比对所有权和已安装哈希，遇未托管冲突或用户修改时拒绝覆盖；安装失败尝试恢复备份；卸载保留修改过的文件/用户改过的默认 Agent。补齐 docs/schemas 安装及与当前源码的版本验证。
- `skills/a-project-archive/scripts/archive_v2.py`：提交前确认远程 baseline，只允许该 snapshot 单个提交的发布/安全重试；发布不可变 SHA，不自动 rebase，不 force push。完整 manifest 校验、忽略文件缺失检查及秘密文件名/内容启发式检查。

### 测试与评估

- `tests/runtime-integration.test.ts` 直接调用生产 `setup()`，模拟 OpenCode 宿主的 tool/permission/session hooks，不再仅验证未被调用的纯状态机。
- 去除已废弃、会把许可误认为完成的 reviewer helper 及相关错误测试；保留实际 pointer 验证和真实适配层回归。
- `evaluations/`：L3 路由、风险、审查失败、过期证据；L4 存量损失、合理删除、错误测试层、架构权衡案例规格。评分必须由独立评估者引用 trace，未运行不算通过。当前没有真实 Agent 分数。

## 3. 验证记录

执行环境：Node 22.16.0、Python 3、TypeScript 5.8.3（环境预装）。

| 验证 | 实际结果 |
|---|---|
| `npm run test:core` | 53/53 通过（含生产适配层模拟集成） |
| Installer Python | 8/8 通过 |
| Project init Python | 7/7 通过 |
| Project archive Python | 11/11 通过（含临时本地 Git bare remote） |
| Model config Python | 3/3 通过 |
| Evaluation scorer Python | 2/2 通过 |
| `npm run verify` | 上述共 84 项测试通过 |
| Core + adapter TypeScript | `tsc --noEmit -p tsconfig.core.json --typeRoots /opt/nvm/versions/node/v22.16.0/lib/node_modules/ts-node/node_modules/@types` 通过 |
| 真正 OpenCode 2.0.32 / provider / L3-L4 | 未运行；环境没有目标宿主与 provider。实际 SDK 入口的兼容性仍需验证 |

TypeScript 类型检查使用预装版本而非 package.json 声明的 5.9.3，不能等同于目标 SDK 类型检查。OpenCode 2.0.32 源码接口已检查；模拟宿主不是实际宿主。见 `evaluations/README.md` 的验收步骤。

## 4. 兼容性、迁移和代价

- 旧 Task 无 receipt，不能直接 resume。保留原记录；新建 ID，继承已确认目标/验收标准，重新验证，不迁移旧 verdict。旧完成记录可作为历史。新版 Task 的人工编辑会被拒绝；不要修改已注册的文件以绕过 Runtime。
- Strict 风险超过 fast/balanced 能力时停止，明确请求用户使用 `/strict`，旧 Task 按情况暂停或取消，建立新 Task。Runtime 只能检查声明风险，不能自动认定所有工程风险，也不能限制任意 shell 编辑。
- Receipt 是框架完整性机制，不是 hostile user 的安全边界。文件和插件存储不能原子跨介质提交；故障后可能 fail-closed，需恢复上一份精确记录或新建 Task。并发独立宿主写入不受支持，避免两个 Session 同时操作同一 Task。
- 证据覆盖当前 worktree、显式文件及 Git 变更；忽略的依赖、外部服务/硬件、共享 worktree 外的需求须另行纳入验证。指纹只证明覆盖对象的新鲜度，不能证明 Agent 真运行了测试；不能保证任意并发写入的原子快照。
- Installer 不再默认覆盖用户自定义文件；遇冲突请先备份、人工合并，再重新安装。历史安装已覆盖的文件无法凭空恢复。备份可能含原配置凭据，验证后按需要清理。
- Archive 要求目标分支有已发布基线；拒绝无关 unpublished commit 和分叉，不再自动 rebase。推送失败可能留下本地 snapshot commit，可按规则重试。启发式 secret 扫描可能误报或漏报，上传前仍要人工确认数据范围。
- 交付 ZIP 为纯源码包，不含原 `.git` 历史、用户 `.vibe`/`.opencode` 会话、机器专用归档路径、依赖和缓存。建议在现有 Git 仓库的新修复分支导入代码，通过 diff 审查后再合并。

## 5. 建议的验收与后续路线

1. 在隔离 OpenCode profile 中先运行现有测试及 `npm install`/`npm run typecheck:core`。
2. 安装候选版，执行 `evaluations/README.md` 中真宿主验收；重点检查 native reviewer result 格式和 hook 调用顺序、跨 Session/restart 及权限行为。
3. 补齐评估场景的可重放夹具，跑真实模型 L3/L4 并独立评分，保存证据。未通过不作为正式发布。
4. 完成后再做 P2：分别讨论三个核心 Skill 的 Mental Model / Analysis Method / Decision Rules / Anti-patterns / Evaluation，而不是仅增加提示词长度。
5. P3 根据实际使用反馈统一跨 Skill 契约并修复剩余审查问题。避免一次性大重构。
