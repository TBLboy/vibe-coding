# Format 3 最终方案：账本进 Git，SQLite 做可重建缓存

> 结论：采纳 GPT 提出的 ledger-first 架构，但砍到 5 个阶段。目标是让"换电脑不丢进度"真正成立，不做多人协作平台。

## 一、最终架构

```text
.project-log/
├── state-format.json                     # {"format": 3, ...}
├── docs/**                               # 长文档，Git 跟踪（不变）
├── ledger/
│   └── v1/
│       └── streams/
│           └── <writer_id>/
│               └── 0000000001-open.jsonl # 追加式事件流，Git 跟踪
├── checkpoints/                          # 本机，gitignore
└── legacy/**                             # format 1 存档（不变）

.git/vibe-state/<project_id>/<context_id>/
└── state.sqlite3                         # 本机缓存，可删可重建
```

职责边界：

```text
Ledger   = 发生过什么 = 唯一持久事实源
SQLite   = 现在是什么 = 投影 / 物化视图 / 缓存
```

核心不变量：

```text
SQLite State == Replay(Git Ledger)
```

## 二、六条设计决定

1. **第一天就用 per-writer stream**，不用单文件 + `merge=union`。
   理由：文本能合并不等于业务状态能合并；每个 writer 独立文件后，并发写入动的是互不相交的文件。这个改动成本极低，事后补救成本很高。

2. **哈希链按 stream 作用域**。
   `prev_hash` / `event_hash` 只在单条 stream 内成链。per-writer stream 加 Git 合并的前提下，全局链不可能成立。

3. **不建立人造的全局绝对顺序**。
   跨 stream 的重放使用确定性排序（`created_at` → `writer_id` → `writer_seq`），真实冲突靠 `aggregate.expected_version` 检出，不靠时间戳或 Last Writer Wins 仲裁。

4. **用 `aggregate.expected_version` 取代全局 `expected_revision`**。
   现状是全局单调计数器（`state_store.py:1543` 与 `metadata["local_revision"]` 比较），跨分支必然误报。实测高层 CLI 自动读取当前 revision（`vibe.py:133`），所以对 Agent 透明，改动主要发生在存储层内部。

5. **Ledger-first 写入**：校验 → 追加账本并 fsync → 更新 SQLite → 返回 receipt。
   账本的持久化追加是唯一 commit point。账本已写而 SQLite 未跟上的情况，启动时增量重放补平。

6. **Checkpoint 不进 Git**。
   它是二进制，不可变只解决合并问题、不解决体积问题。账本才是事实源，重建是兜底。只有在重放明显变慢时才在本机启用。

## 三、事件结构

```json
{
  "schema_version": 1,
  "command_id": "全局唯一",
  "writer_id": "本副本写入流",
  "writer_seq": 42,
  "action": "task.finish",
  "aggregate": {"type": "task", "id": "TASK-031", "expected_version": 7},
  "request": {},
  "receipt": {},
  "created_at": "2026-09-21T12:00:00Z",
  "prev_hash": "同一 stream 上一条的 event_hash",
  "event_hash": "本条规范化序列化后的 sha256"
}
```

重放确定性要求：时间、随机 UUID、文件哈希、测试结果等外部可变数据，必须在命令被接受时写入 `request` 或 `receipt`，重放时禁止重新计算。

## 四、实施阶段

### Phase 0：Golden Replay Test（安全网，不改任何行为）

- 把现有 `_verify_ledger()` 的重放逻辑抽成可复用的 `reduce(ledger) -> state`。
- 以现有 189 条命令为基线：从空状态重放，必须逐表等于当前 SQLite。
- 产出 `logical_state_hash` 作为迁移基准。
- 验收：测试通过，且故意篡改一条命令必须让它失败。

### Phase 1：导出账本（纯增量，不改写路径）

- 把 189 条命令无损导出到 `.project-log/ledger/v1/streams/<writer_id>/0000000001-open.jsonl`。
- 不修改 `command_id` / `request` / `receipt` / `created_at`，不清洗历史。
- 验收：`reduce(导出账本) == 当前 SQLite`；`git add` 后在新 clone 中能看到全部历史。
- **做到这一步，G1 已经完成大部分**：完整历史进入 Git。

### Phase 2：重建路径

- `vibe state-attach` 语义改为：读账本 → 校验结构与哈希链 → 重放 → 构建全新 SQLite。
- 启动对账：比较账本 frontier 与 SQLite frontier；落后则增量重放，哈希不符则整体重建。
- 验收：干净 clone 执行 `state-attach`，状态与源机逐表一致。

### Phase 3：Ledger-first 写入

- `Store.apply()` 改为账本优先；同时把全局 `expected_revision` 换成 `aggregate.expected_version`。
- 崩溃恢复覆盖三种点：append 前、append 后 SQLite 前、两者完成后。
- 验收：三种崩溃点都有测试；并发冲突被显式检出，而不是被静默覆盖。

### Phase 4：可移植性守卫

- 新增 `vibe portability-status`，输出 `ledger_tracked` / `uncommitted_ledger_changes` / `unpushed_commits` / `portable`。
- 接进 session 收尾与 handoff：账本未提交就明确提示。
- 验收：故意不 commit 时状态必须显示 not portable。

### Phase 5：延后项（触发式，不阻塞上线）

| 项目 | 触发条件 |
|---|---|
| Segment 切分 | 单条 stream 超过约 1 MB |
| 冲突解决命令 | 真的出现并发写同一聚合体 |
| 本机 Checkpoint | 全量重放超过约 1 秒 |

## 五、明确不做

- 不把整个系统改成 CRDT（状态机转换必须显式冲突）。
- 不做多人协作的完整冲突解决 UI。
- 不把 checkpoint 提交进 Git。
- 不引入 Dolt / TerminusDB。
- 初期不做历史截断或 log compaction。

## 六、迁移路径

- format 1 项目：沿用现有 `vibe migrate`，1 → 2 → 3，现有工具不动。
- format 2 项目：Phase 1-3 即是 2 → 3 的迁移。
- 保留 format 2 的 exchange 代码作为过渡期兜底，Phase 3 完成后停止使用。

## 七、风险与回退

| 风险 | 缓解 |
|---|---|
| 重放不确定 | Phase 0 的 Golden Replay Test 作为门禁，外部数据必须入账本 |
| 迁移丢历史 | 导出是纯增量；`legacy/` 与 format 1 存档全程不动 |
| 并发写冲突 | 检测并显式报告，不自动仲裁、不覆盖 |
| 架构改造过大 | 每个 Phase 可独立停止；Phase 1 之后即使停手，也已获得 Git 中的完整历史 |

回退方式：账本目录是新增产物，删除 `.project-log/ledger/` 并保留 format 2 交换代码即可退回原状态。

## 八、两个不需要现在回答的问题

1. **是否会两台机器并发写同一项目**：不影响 Phase 0-4。per-writer stream 已让并发写在最坏情况下变成"显式冲突报告"，不会损坏数据。
2. **是否需要 segment / checkpoint**：由 benchmark 触发，不靠预判。
