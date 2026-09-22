---
name: b-background-task-runner
description: Execute long-running shell commands in background without blocking the agent, with persistent logging and progress checking.
license: MIT
compatibility: codex
metadata:
  stage: operational
  output: background-process
---

# Background Task Runner

## Purpose

标准化的后台任务执行模式：当命令预计耗时 >15 秒且不依赖 ephemeral shell 状态时，用 nohup + log 重定向后台运行，让 Agent 可以立即返回对话而不被阻塞。

## When to Use

### 必须后台执行（全部满足）

- 预计执行耗时 **>15 秒**（构建、测试、安装、下载、训练等）；
- **且** 不依赖当前 bash 会话的临时状态（`export`、`cd`、`source venv/bin/activate`、临时变量等）；
- **且** 不需要交互式输入；
- **且** 不需要立即捕获输出来做下一步决策。

### 仍使用同步 bash()

- 需要交互式输入；
- 依赖前一条命令的 shell 状态（venv 激活、cd、export 等）；
- 预计 15 秒内完成；
- 需要立即解析输出用于下一步决策。

## Standard Execution Pattern

### 1. 启动后台任务

```bash
nohup <command> > <persistent-log-path> 2>&1 &
echo "PID: $!"
```

- 日志文件必须存放在持久化位置（如项目目录下），**不要放在 `/tmp/`**
- 使用 `python3 -u` 禁用输出缓冲（对 Python 脚本）
- 记录 PID 以便后续管理

### 2. 验证启动

```bash
sleep 5 && head -5 <log-path>
```

### 3. 检查进度

```bash
# 进程是否存活
ps -p <PID> -o pid,state,etime,cmd --no-headers

# 日志最新输出
tail -20 <log-path>

# 已生成文件数（适用于下载/转换任务）
ls -d <output-dir>/*/ 2>/dev/null | wc -l

# 磁盘占用
du -sh <output-dir>
```

### 4. 停止任务

```bash
kill <PID>
# 或按名称批量停止
pkill -f <script-name>.py
```

## Output Tracking Convention

后台任务执行后，agent 应在 `.project-log/current-session.md` 中记录：
- PID
- 启动时间
- 日志路径
- 预期完成条件（如"下载 149 个 episodes"）
- 最近一次检查的结果

## Examples

### 下载数据

```bash
nohup python3 -u download_data.py > /project/training-data/download.log 2>&1 &
```

### 安装依赖

```bash
nohup pip install -r requirements.txt > /project/install.log 2>&1 &
```

### 训练

```bash
nohup python3 -u train.py --config config.yaml > /project/training/train.log 2>&1 &
```

## Anti-Patterns

- ❌ 用 `task()` 子 Agent 跑后台命令（子 Agent 无 shell 权限，实际行不通）
- ❌ 用 `sleep N; command` 串行等待
- ❌ 日志写到 `/tmp/`（会话重启后丢失）
- ❌ 不检查是否真正启动成功就返回
