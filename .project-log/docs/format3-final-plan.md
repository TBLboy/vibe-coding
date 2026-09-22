# Format 3 最终方案（2026-09-22 定稿）

> 目标：工程日志自动记录、随 Git 提交、换机后可完整恢复；同时保留 `vibe` CLI 的结构化快速写入。
> 使用者为单人，日志单向增长，不存在多人并发修改同一工程。

## 一、最终架构

```text
work/                              # 普通目录，本身不是 Git 仓库
├── .project-log/                  # 普通目录，本身不是 Git 仓库
│   ├── ledger/                    # 追加式账本，Git 跟踪（经 KB）
│   ├── docs/                      # 长文档正文，Git 跟踪（经 KB）
│   ├── state-format.json          # 格式标记
│   ├── .gitignore                 # 忽略 .state/
│   └── .state/                    # 本机 SQLite 缓存，永不归档
├── AGENTS.md
├── repo-a/                        # 独立代码仓库
└── repo-b/                        # 独立代码仓库
```

职责边界：

```text
Ledger   = 发生过什么 = 唯一持久事实源
SQLite   = 现在是什么 = 投影 / 缓存，可删除、可重建
KB 仓库  = 日志的远端载体 = 传输通道
```

核心不变量：

```text
SQLite State == Replay(Git Ledger)
```

## 二、与 GPT 提案的差异（砍掉了什么）

GPT 的 Format 3 提案面向"多人、多分支、多 Agent 长期协作"。本方案的使用者是单人、日志单向增长，因此砍掉：

| 砍掉项 | 原因 |
|---|---|
| Per-writer stream | 单写入者，单条线性账本即可 |
| `aggregate.expected_version` 冲突仲裁 | 无并发写，保留全局 `expected_revision` 做完整性校验即可 |
| 冲突解决命令 | 无并发冲突可解决 |
| CRDT 边界 | 不涉及 |
| Sealed segment / 切分 | 体量远未到阈值 |
| Git 跟踪 checkpoint | 二进制进 Git 与目标矛盾 |

保留的核心只有三件：**追加式账本 + 可重建 SQLite + 增量重放**。

## 三、六条设计决定

1. **`.project-log` 是普通目录，不是 Git 仓库。**
   做成仓库会引入归档时的 gitlink 陷阱（见第七节），且本地无远端仓库不提供任何耐久性。

2. **日志的远端载体是知识库（KB）仓库。**
   归档时把 `.project-log` 的内容复制进 `<kb>/工程记录/<work文件夹名>/.project-log/`，由 KB 提交推送。

3. **账本路径与 identity 必须与分支无关。**
   现状 `context_id` 把分支名算进 identity（`state_context.py:94` 的 `branch_hex`），导致切换分支后日志"消失"。Format 3 必须改成项目级。
   注：work 目录本身不是 Git 仓库时，identity 已使用 `branch: "local"`，天然与分支无关；本条要求在该前提下保持不变。

4. **归档排除 SQLite。**
   只归档 `ledger/`、`docs/`、`state-format.json`、`.gitignore` 与派生视图；排除 `.state/`、`.git`、`legacy/new-writes/`。

5. **归档是合并追加，不是整份替换。**
   按 `command_id`（`uuid.uuid4().hex`，全局唯一）去重后追加。归档前校验本地账本是 KB 的超集，不是则拒绝并报告差异。

6. **项目名 = work 文件夹名**（用户指定）。归档时若目标已存在且 `project_id` 不同，必须拒绝而不是静默覆盖。

## 四、工作流

### 日常

```text
1. mkdir work && cd work
2. vibe init                      # 生成 .project-log（普通目录）
3. 在 work 下克隆代码仓库
4. 开发 —— 日志自动写入 .project-log/ledger/，切分支不影响
5. 每个工作段落结束：归档这个工程
```

归档不是"出差时才做"。它是日志唯一的持久化点，应与提交代码同等频繁。

### 归档

```text
1. 校验本地账本是 KB 副本的超集
2. 复制 ledger/ docs/ state-format.json .gitignore（排除 .state/、.git）
3. 按 command_id 合并追加进 <kb>/工程记录/<work名>/.project-log/
4. KB 内 git add / commit / push
```

### 换机

```text
1. 建立 work 目录
2. 逐个克隆代码仓库
3. 克隆 KB
4. 对齐项目进度：把本项目日志从 KB 合并进 work/.project-log
5. vibe state-attach：从账本重放构建本地 SQLite
6. 继续开发
```

## 五、实施阶段

| 阶段 | 任务 | 内容 | 状态 |
|---|---|---|---|
| Phase 0 | TASK-048 | Golden Replay Test：抽出 `reduce(ledger) -> state`，用现有命令建立 `logical_state_hash` 基线 | implemented-unverified |
| Phase 1 | TASK-049 | 把现有命令无损导出为 Git 跟踪的账本 | implemented-unverified |
| Phase 2 | TASK-050 | `state-attach` 从账本重放建库 + 启动对账（支持增量重放） | implemented-unverified |
| Phase 3 | TASK-051 / TASK-061 | 切换 Ledger-first 写入（TASK-051 的 per-writer 变体已取消，TASK-061 为项目级账本版本） | implemented-unverified |
| Phase 4 | TASK-052 | `portability-status` 与收尾守卫 | implemented-unverified |
| — | TASK-058 | 修复归档 skill：排除 `.state/`/`.git`、项目名撞车检测、合并追加、超集校验 | implemented-unverified |
| — | TASK-059 | 新增"对齐项目进度" skill：从 KB 合并日志进 work 并触发 SQLite 重建 | implemented-unverified |
| — | TASK-060 | 账本路径与 identity 与分支无关 | implemented-unverified |

全部阶段已在框架 0.6.0 落地，并由 182 个 unittest（1 个跳过）与
`validate_package.py` 覆盖；四个收尾任务（TASK-058/059/060/061）的完成门禁均为 `allowed`。

## 六、明确不做

- 不把 `.project-log` 做成 Git 仓库
- 不把 SQLite 或 checkpoint 提交进 Git
- 不做 per-writer stream、冲突仲裁、CRDT
- 不做 segment 切分与历史截断
- 不引入 Dolt / TerminusDB

## 七、已实测的关键事实（方案依据）

| 事实 | 证据 |
|---|---|
| 非 Git 的 work 目录下 `vibe init` 正常，SQLite 落在 `.project-log/.state/<project_id>/<context_id>/` | 实机复现 |
| 非 Git 目录下 identity 使用 `branch: "local"`，不随分支变化 | `state_context.py:65-68` |
| Git 仓库内切换分支会改变 `context_id`，日志"消失"需 `state-attach` + `state-import` | 本仓库 main→codex 切换实测 |
| `.project-log` 若是 Git 仓库，归档 `copytree` 会把 `.git` 复制进 KB，KB 侧 `git add` 产生 gitlink（`mode 160000`），日志内容一条都进不了仓库 | 实机复现 |
| `exchange export` 在非 Git 目录直接报 `git_context_error`，现有快照机制在 work 布局下不可用 | 实机复现 |
| `command_id` 由 `uuid.uuid4().hex` 生成，全局唯一，可作为跨机器去重键 | `vibe.py:132` |

## 八、风险与回退

| 风险 | 缓解 |
|---|---|
| 归档替换语义导致 KB 静默丢记录 | 改为按 `command_id` 合并追加 + 超集校验 |
| 两台机器各自有未归档进度 | 归档前超集校验会拒绝；对齐 skill 先合并再开工 |
| 重放不确定 | Phase 0 Golden Replay Test 作为门禁；时间、随机值、文件哈希等外部数据必须入账本 |
| 项目名撞车 | 归档时比较 `project_id`，不同则拒绝 |
| 架构改造过大 | 每个 Phase 可独立停止；Phase 1 之后即已获得 Git 中的完整历史 |
| 换机重建依赖 Phase 2 | Phase 2 完成前，换机恢复仍使用现有 `state-export`/`state-import` 快照机制 |

## 九、已知边界

- 账本可按 `command_id` 自动合并；`docs/` 下的手写长文档是可修改文件，无法自动合并，冲突时需人工比对 KB 的 Git 历史。
- 日志的持久化点就是归档。两次归档之间的日志只在本机，归档频率应等同于提交代码的频率。
