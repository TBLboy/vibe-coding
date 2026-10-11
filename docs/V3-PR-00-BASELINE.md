# V3 PR-00 基线冻结与失败反例（可复现材料）

- **制定日期**：2026-10-10
- **分支**：`v3`（从 `opencode-main` @ `699a2f60` 拉出；`V2正式版本` 标签固定在 `opencode-main`，未移动）
- **任务书**：`Vibe-Workflow-V3-工程改造实施方案.md` §8 PR-00、§12 启动指令
- **范围声明**：本 PR **未改变任何产品行为**。只新增失败反例测试、契约测试与本文档。没有修改 `state_store.py` / `state_replay.py` / `vibe.py` / 任何 Skill 或 Agent。

---

## 1. 已核验的源码基线

| 项 | 文档声明 | 实测 | 结论 |
|---|---|---|---|
| `runtime/scripts/state_store.py` | `2190101de1dc51cb0904fc80ea57b4d9c330d86c56258196035e86f6f1e611d6` | 同 | **一致** |
| `runtime/scripts/vibe.py` | `2a3842adf74590d7e35e3357d47901ea4e2da5e03e46cff6d84b1070b1a68365` | 同 | **一致** |
| `test_state_gates.py` | 21 | 21 | **一致** |
| `test_state_replay.py` | 5 | 5 | **一致** |
| `test_command_surface.py` | 7 | 7 | **一致** |

指纹比对方式：用正则**直接从文档原文提取** 64 位十六进制串再与文件 sha256 比较，不经过人工转录（首次比对曾因人工转录打错一个字符而误报不一致，已更正）。

### 1.1 版本与结构常量（本 PR 未改动）

```text
runtime/scripts/state_store.py:14   SCHEMA_VERSION = 1          # 命令 envelope
runtime/scripts/state_store.py:16   STORE_SCHEMA = 3            # SQLite 投影
runtime/scripts/state_store.py:23   MAX_DOCUMENT_BODY_CHARS = 4096
runtime/scripts/state_store.py:451  _BUNDLE_COLUMNS = {...}
runtime/scripts/state_store.py:468  _BUNDLE_FIELDS = {"schema_version","project_id","context_id","local_revision","base_snapshot"} | set(_BUNDLE_COLUMNS)
runtime/scripts/state_ledger.py:27  LEDGER_SCHEMA_VERSION = 1   # 账本事件外壳，与 STORE_SCHEMA 不是同一个版本概念
```

关键约束（PR-01/02/05 会动到，先记录）：

```text
state_store.py  runs 表: id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES tasks(id)
state_store.py          CREATE UNIQUE INDEX one_active_run ON runs(status) WHERE status = 'active'
state_store.py:1561     "task.begin": {"ready"}          # 终态无法回到 in-progress
state_store.py:1604     task.finish 无条件写 implemented-unverified
state_store.py:1128     _goal_completion_problems 调用 _document_drift_problems
state_store.py:1239     _document_drift_problems: SELECT kind, id, payload FROM records ORDER BY kind, id
```

> **文档未提到的一点**：`runs` 上除 `task_id UNIQUE` 外，还有 `one_active_run` 这个**全局部分唯一索引**（同一时刻只能有一个 `active` Run）。它不阻塞 N03 的"新 Task 继承旧 Task"重开方案（旧 Run 已是 `finished`），但长期若要支持并发任务会撞上，建议在 PR-05 的 reopen 设计里显式登记。

### 1.2 既有测试基线（完整复现）

```text
python -m unittest discover -s tests -q   →  Ran 261 tests, OK (skipped=8), 191.9s
```

---

## 2. 新增的失败反例（5 条，全部按预期为红）

约定：使用 `@unittest.expectedFailure`。测试**确实失败**，但套件保持可判读（`OK (expected failures=N)`）；修复落地后它会"意外通过"，从而**强制**移除装饰器，而不是让检查被遗忘。

| 测试 | 位置 | 缺陷 | 目标行为（修复后） |
|---|---|---|---|
| `test_high_risk_goal_rejects_foreign_task_review` | `tests/test_state_gates.py` | N01 | 高风险 Goal 不得被其它 Goal/任务的 Review 放行 |
| `test_high_risk_goal_without_implementer_fails_closed` | `tests/test_state_gates.py` | N01 | 未登记 implementer 的高风险 Goal 必须 fail-closed |
| `test_unrelated_doc_ref_drift_does_not_block_an_unrelated_task` | `tests/test_state_gates.py` | D05 | 无关文档漂移不得阻塞当前任务 |
| `test_skill_invocations_resolve_to_the_real_cli` | `tests/test_skill_cli_contract.py` | N02 | Skill 写的每条命令都必须真实存在（含 `--flag`） |
| `test_skill_record_kinds_exist` | `tests/test_skill_cli_contract.py` | N02 | Skill 写的每个 record kind 都必须存在 |

### 2.1 原始观测值（不经断言，直接打印）

```text
=== N01a：高风险 Goal 用【另一个 Goal 的任务复核】是否能通过 ===
    evaluate_goal("GOAL-A") = {'goal_id': 'GOAL-A', 'passed': True, 'reasons': []}
    期望（PR-01 后）: passed=False（复核归属不符）
    当前实际: passed=True  ← 缺陷：被无关任务/目标的复核放行

=== N01b：高风险 Goal 未登记 implementer 时是否 fail-closed ===
    evaluate_goal("GOAL-A") = {'goal_id': 'GOAL-A', 'passed': True, 'reasons': []}
    期望（PR-01 后）: passed=False（missing_implementer）
    当前实际: passed=True  ← 缺陷：缺 implementer 时独立性判据整段被跳过
    对照：高风险【任务】缺 implementer 时任务门禁的行为（应 fail-closed）
      gate_task("TASK-H") = {'task_id': 'TASK-H', 'decision': 'blocked',
        'blocking': ['high-risk task TASK-H has no recorded implementer, so reviewer
                     independence cannot be established',
                     'high-risk task TASK-H lacks a go review from an independent reviewer']}

=== D05：与任务无关的文档漂移是否阻塞该任务 ===
    文档修改前: decision = allowed | blocking = []
    文档修改后: decision = blocked | blocking = ['record research/RES-DOC payload.doc_ref:
        doc_ref changed: recorded b3ec2cf0c034, current da3a266a5a84']
    期望（PR-03 后）: 修改后仍 allowed（无关文档不阻塞）；当前: 被阻塞 ← 缺陷
    validate 是否也报告该漂移: ['record research/RES-DOC payload.doc_ref: doc_ref changed: ...']

=== N02：Skill/Command 引用的命令与 record kind ===
    违规项:
      - skills/a-business-clarify/SKILL.md: `vibe task create` -> exit 2
      - skills/a-business-clarify/SKILL.md: record kind `open-question` 不在 RECORD_KINDS 中
```

对照之所以有力：**同一个"缺 implementer"场景，任务门禁是 `blocked` 且错误信息准确**，而 Goal 门禁返回 `passed: True, reasons: []`。根因在 `state_store.py:1196-1213`——整段独立性判据被包在 `if type(implementer) is str and implementer.strip():` 里且**没有 else 分支**。

`RECORD_KINDS` 现有取值：`alignment / architecture / business-atom / decision / distillation / requirement / research / retrospective`（无 `open-question`）。

---

## 3. 与任务书不一致的决策（按 §0.6 记录）

### 3.1 迁移夹具：改放仓库之外，且不提交真实账本

任务书 PR-00 要求"复制旧账本/SQLite 快照到仅用于测试的夹具"。实测与决策：

- 覆盖全部动作类型的最短真实前缀约 **1.05 MB**（497/806 事件），完整账本 1.70 MB、SQLite 3.23 MB。
- 仓库 `github.com/TBLboy/vibe-coding` 是**公开**仓库。把真实账本提交进去等于**发布用户的历史数据**，属于 C 级发布决定，超出本 PR 权限。
- 因此本 PR 的处置：把快照复制到**仓库之外**的本地目录 `D:\Project\vibe-coding\.v3-legacy-fixture\`（`ledger.jsonl` 1,701,517 B + `state.sqlite3` 3,231,744 B），源文件未改动；**不加入任何 `.gitignore`、不进入 git 索引**。
- 待你决定（PR-06 前需要）：夹具是否允许入库？三选一 —— (a) 保持仓库之外、只在本地做迁移演练；(b) 提交**压缩后的真实前缀**（约 100 KB）；(c) 改为测试内生成**合成账本**（无真实数据、可公开、体积最小）。
- **已裁决（DEC-048，2026-10-10）**：取 (a)。拒绝 (b)：公开仓库里提交真实历史数据不可逆，而同等保真度在本地已具备；(c) 的目标（无真实数据、可公开、可重复）已由 `tests/test_upgrade_recovery.py`（手搓 schema-3 投影）与 `tests/test_state_replay.py`（账本/回执等价）达成，故不新增合成夹具。
- **复演结果（TASK-123，2026-10-10）**：该快照的 store 绑定其**原始 root 路径**——`context_id` 由 `{"root": <绝对 root>, "branch": "local"}` 派生。把快照搬到另一个 root 时，schema 3 → 4 的**原地升级确实成功**（806 事件全部重建、revision 806、`tasks` 102 行），且账本字节完全未变（`ledger.jsonl` SHA-256 `0872d4d0ba0a4f83a22495b2dbeffa6c53b85c50c8395e3cab4a62d862d161fc` 前后一致，1,701,517 B）；但随后 `status` / `validate` / `ledger verify` 一律以 `context_mismatch` 拒绝——**store 拒绝被静默迁移**，这是设计上的安全属性，不是缺陷。因此：§3.1 里"只在本地做迁移演练"应读作"**在原 root 路径上**"；跨目录复演需要另行设计（例如只带账本、由新 root 重建投影），本次未实现。仓库外的夹具目录名（`2428c28d…`）只在原 root 下有效。

### 3.2 `expectedFailure` 而非裸红

任务书要求"保持新测试初始失败（红）"。裸红会让此后每个 PR 的测试运行都不可判读，也可能掩盖真实回归。改用 `expectedFailure`：红是**显式登记**的，套件仍能反映其它回归，且修复后会自动"意外通过"逼出装饰器移除。

---

## 4. 交给后续 PR 的交接项

- **PR-01**：`state_store.py:1187-1213` 需要按 §5.2 的六条最小不变量重写；错误码区分 `missing_implementer` / `review_scope_mismatch` / `review_evidence_stale` / `review_missing`。两条 N01 反例转绿后**必须移除** `@unittest.expectedFailure`。
- **PR-03**：`tests/test_state_gates.py::test_changed_doc_ref_propagates_into_task_and_goal_gates` 断言的是**当前的全局行为**，与本 PR 新增的 D05 反例互相矛盾；PR-03 必须把它改写成"相关受控文档才 fail-closed（T19）+ 信息性引用不阻塞（T20）"。
- **PR-05**：N02 的两处违规（`vibe task create`、`open-question`）需二选一——公开真实入口，或把 Skill 改指向合法入口。另注意 `runs.one_active_run` 全局唯一索引。
- **PR-06**：迁移演练使用 §3.1 的夹具路径；另见待你决定的发布方式。

---

## 5. 如何复现

```bash
# 基线
python -m unittest discover -s tests -p 'test_state_gates.py' -q      # Ran 24, OK (expected failures=3)
python -m unittest discover -s tests -p 'test_skill_cli_contract.py' -q  # Ran 2,  OK (expected failures=2)
python -m unittest discover -s tests -q                               # 完整套件

# 原始观测值（打印而非断言）
python <本机脚本>  # 见 PR 描述中的 pr00_reproduction 输出，已摘录于 §2.1
```
