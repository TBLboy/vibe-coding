# Vibe Coding V2 — P2 工程方法论深化计划与交付说明

基线：`vibe-coding-P0-P1-repaired.zip`。本次为 P2 源码候选版，不宣称通过目标 OpenCode 宿主验收或真实 Agent 能力评估。保留原 P0/P1 交付记录 `REPAIR_PLAN.md`，其 P2 状态为当时的历史记录。

## 1. 范围与实施计划

目标不是给 Skill 增加更多检查项，而是形成可执行的工程推导过程。按设计 → 实施 → 验证组织三个 Skill，方法独立、产物可衔接，但不形成强制工作流。

| 任务 | 实现 | 验收证据 |
|---|---|---|
| P2-01 架构决策 | 从当前架构、需求、约束推导边界、方案和权衡 | Skill + worked example；2 个 L4 场景 |
| P2-02 工程落地 | 存量保护、最小完整变更、真实生产接入、前后向核对 | Skill + worked example；2 个 L4 场景 |
| P2-03 工程验证 | 可证伪命题、真实被测对象、独立 oracle、测试设计与证据有效性 | Skill + worked example；2 个 L4 场景 |
| P2-04 框架衔接 | Main Agent/Agent Contract 引导按需加载；不强制三段流程 | 现有路由/结构测试，安装引用文档检查 |
| P2-05 评估与交付 | 6 个可重放场景、3 个可运行夹具、Git 基线、独立评分 | 夹具自测、评分器自测、回归测试；真实模型待运行 |

非目标：P3 Skill 深化、重新设计 Runtime、引入新模式/Agent/Task 字段/存储、强制生成变更账本文件、自动提交或部署。此次不修改 P0/P1 的安全边界和迁移规则，也不替代真实宿主验收。

## 2. 三个核心思维模型

### 2.1 `a-architecture-decision` — 从描述架构到推导架构

当前系统 → 架构驱动/不变量 → 职责与变化方向 → 可行方案 → 权衡与反证 → 边界/契约 → 落地和验证。

核心方法：追真实入口、状态归属、依赖方向；按共同变化原因和不变量划分职责；将质量属性落实为场景和可观察响应；比较最小扩展和可信替代方案；识别失败路径、迁移和退出成本；高影响未知用 spike 验证，不凭空发明性能指标或未来需求。A/B/C 权限不变；C 决策未批准不能视为设计完成。

示例：HTTP 增加队列传输时，比较局部分支、窄 transport port、动态插件框架。明确状态归属、错误契约、旧默认及不确定的 ack/idempotency；不因未来可能增加第三个实现就默认采用插件框架。

### 2.2 `a-engineering-landing` — 从完成新功能到控制系统变更

还原存量 → 变更/保留账本 → 最小完整增量 → 保护基线 → 分片实现 → 处理偏离 → 正反向核对 → 验证交接。

关键要求：每个被删除的职责明确替代、经授权退休或未知；新功能必须覆盖调用、注册、配置和失败路径，不能仅实现未接入的 helper；保留旧默认、接口、错误处理及用户未提交改动。新发现的语义/公共接口等 C 决策不自行批准。兼容性变化可用 expand/migrate/contract，不强制任何架构模式。

修正原 Skill 的生命周期歧义：`begin_implementation` 仅在 `prepare` 调用；已经处于 `implement` 的恢复/修复路径不重复调用。保持风险独立于 mode；严格风险必须请求明确 `/strict` 并建立新 Task。严格 policy 即使低风险仍需 reviewer。

### 2.3 `a-verification` — 从跑测试到构建证据

验收命题 → 失败假设 → 实际被测对象 → 独立 oracle → 测试方法与层级 → 测试有效性 → 结果诊断与证据。

针对输入边界、状态转换、契约、重构、故障/并发、属性不变量及迁移给出方法选择规则。测试层级不是等级竞赛：最小充分层级优先，生产接入风险必须覆盖真实调用路径。重要命题可用隔离反例、已知失败基线或可逆变异检查测试能否检出缺陷，不强制所有任务做 mutation testing。最终绑定产物后再执行验证，缺失必要证据不得完成。产物指纹仍只是新鲜度证据，并不证明测试执行。

示例：纯状态机单测全绿，生产 handler 绕过状态机直接写状态。验证必须调用 handler，断言非法转换报错、状态不变且没有副作用，不能用调用次数或单测数量代替。

## 3. Skill 之间的衔接与框架约束

需求/约束 → 架构决策（为什么、边界、不变量） → 现有工程规格/Task（具体契约与验收） → 工程落地（真实调用链及存量） → 工程验证（独立 oracle 与证据）。这是信息传递关系，不是必须依次加载所有 Skill 的工作流。小任务仍可直接实现和针对性检查；重大任务在当前上下文或现有 spec/Task 复用上述信息，不引入新持久化格式。Reviewer 仍只在 strict 下由 Runtime 授权。

每个 Skill 保留原 frontmatter、中文路由、V2 operating rules 和记忆契约。核心方法在 SKILL.md；worked example 与进一步参考在相对 `references/`，通过现有 installer 部署。Main Agent/Agent Contract 仅增加按需使用指引，Runtime TS、Task Schema、产品状态机及安装器实现均不变。

## 4. 能力评估

| Case ID | 应检验的行为 |
|---|---|
| p2-architecture-concrete | 真实架构、约束、方案权衡、不过度设计、不假设 exactly-once |
| p2-architecture-authority | 不擅自改重复订单语义；发现 C 级冲突 |
| p2-landing-wiring | 完整注册新策略，旧默认/公共接口回归，保留未提交用户编辑 |
| p2-landing-scope | 公共接口退休与迁移未确认时不直接删除 |
| p2-verification-ingress | 单测全绿仍发现生产入口绕过；能写出实际失败的集成测试 |
| p2-verification-oracle | 不接受仅“无报错”的弱 oracle 作为完整证据 |

三套 Python 小项目：architecture / landing / verification。使用 Python 3 + Git，无第三方依赖。`prepare_p2.py` 生成独立 Git 仓库和基线 SHA；不覆盖已有目录。评估脚本输出 prompt 和 setup；不要将评分标准暴露给被评估 Agent。原 8 个 P1 案例全部保留，当前总计 14 个案例，新增 6 个有可运行夹具。实际评估须在隔离宿主上使用固定模型、配置，保留 trace/diff/测试证据，每个场景独立重复、独立评分。没有评估结果不算通过。

## 5. 验证与限制

本地 Node 22.16.0、TypeScript 5.8.3、Python 3、Git。现有 TS 53 项、Python 原有 31 项、新增夹具自测 3 项，共 87 项。安装回归额外断言三个 reference 字节一致。夹具自测覆盖所有六个场景、Git 基线、用户未提交改动及故意植入的缺陷可复现。类型检查使用环境预装 tsc/Node types，非目标 SDK 实际宿主。详见最终验证记录。

没有运行 OpenCode 2.0.32 / provider，也未运行真实 L3/L4 模型。不能以静态内容、测试行数、夹具自测证明 Skill 的真实能力有所提升；需要与 P0/P1 基线在同一批夹具/模型上进行对照评估（基线也可使用本版夹具，但应隔离，避免暴露评分标准）。尚未实现自动化模型运行器；现有评分脚本聚合独立评估结果。P1 原有八个案例仍是人工准备规格。

发布前按 `evaluations/README.md` 执行真实宿主验收和模型评估；建议对照正确性、漏报/误报、无授权变更、测试有效性及额外调用/时间成本。若 P2 在低风险任务增加不必要的流程，收敛加载和输出规则，不新增状态。

## 6. 参考来源

- [SEI, Architecture Tradeoff Analysis Method](https://www.sei.cmu.edu/library/the-architecture-tradeoff-analysis-method-collection/)：质量场景、冲突质量属性及权衡。此处是轻量适配，并非完整 ATAM。
- [Martin Fowler, Parallel Change](https://martinfowler.com/bliki/ParallelChange.html)：不兼容接口的渐进演进。
- [Google, Test Behavior, Not Implementation](https://testing.googleblog.com/2013/08/testing-on-toilet-test-behavior-not.html)：围绕可观察行为而非实现细节测试。
- [Google, What Makes a Good End-to-End Test?](https://testing.googleblog.com/2016/09/testing-on-toilet-what-makes-good-end.html)：关键用户路径与 E2E 维护成本。

P3 暂未实施。P2 的主要设计选择是“加深思维模型，不增加强制工程仪式”，以及将真实能力评价作为独立门禁。

### 最终本地验证记录

- `npm run verify`：退出码 0，TS 53/53；Python installer 8/8、init 7/7、archive 11/11、model config 3/3、scorer 2/2、fixture 3/3。
- `tsc --noEmit -p tsconfig.core.json --typeRoots /opt/nvm/versions/node/v22.16.0/lib/node_modules/ts-node/node_modules/@types`：退出码 0。
- 与基线 ZIP 逐文件 SHA-256 比较：修改 12 个文件，新增 22 个文件，删除 0 个；无 Runtime TypeScript、Task Schema 或安装器实现变化。
