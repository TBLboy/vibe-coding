---
name: b-project-structure-survey
description: "梳理目录结构/工程结构地图/把握工程大局观/模块依赖梳理 · Produce a concise, evidence-grounded static map of an unfamiliar repository's organization: where things live, what depends on what, where boundaries are, and how new code is usually added."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# Project Structure Survey

## Purpose

Read an unfamiliar repository cheaply and return a **structural map**: how the code is organized, not how the system behaves.

The product is a cognitive map, not a development manual. It answers four questions:

1. **Where is it** — the main modules, configuration, entry points, tests.
2. **Who depends on whom** — the observable static dependency direction between modules.
3. **Where are the boundaries** — how the project separates public interfaces from internal implementation.
4. **Where does new code usually go** — the organization and extension conventions the existing structure reveals.

Question 4 describes conventions only. It never prescribes file-level placement for a task the user has not yet named.

## What this Skill does not do

- Does not explain business logic, end-to-end runtime flow, or function implementations.
- Does not read files line by line, and does not teach code.
- Does not run the project, build it, test it, or modify the repository.
- Does not evaluate code quality or propose refactors.
- Does not produce task plans, change-impact lists, or multi-day reading plans.
- Does not guess a module's purpose to fill a template.

## Boundary with adjacent capabilities

| Skill | Question | Product |
|---|---|---|
| `b-project-structure-survey` | How is the project organized? | Static structure map |
| `a-codebase-onboarding` | How does the system work? | Business/runtime semantics, evidence, risks |
| `b-source-code-tutoring` | How does this code work? | Explanation of specific source |

They may be used in sequence when the user asks, but this Skill does not automatically hand off, and its output carries no teaching or implementation sections.

## Triggers

Route here when the user asks about organization: "梳理一下这个工程的目录结构", "给我一张工程结构地图", "这个仓库主要模块是什么、怎么组织的", "快速了解这个项目的大局".

Do not route here for "怎么修这个 bug", "这个函数怎么运行", "怎么实现某功能" — those belong to other capabilities. Automatic routing never means automatically writing a file.

## Method: breadth first, cheap, limited depth

### Round 1 — skeleton

Identify the language, the package root, the main top-level directories, the size distribution, and the project's stated purpose from its README. Exclude noise: `.git`, virtual environments, dependency caches, build output, generated artifacts.

### Round 2 — relationships

Read package-level declarations, a small number of entry points, and configuration locations. Summarize the static dependency direction between the main modules. Stop at the depth needed to explain module purpose and relationships.

### Round 3 — compress

Merge minor directories, cut repeated information, mark what could not be confirmed from static evidence, and write a short document.

Use only read-only means: directory listing, `find`, `rg`, and light scripts. Commands in this Skill are illustrative — adapt them to the actual language, tooling, and layout. Do not turn a Python-specific command into a cross-language rule.

```bash
# size distribution — the only quantitative signal that matters
find . -name "<ext>" -not -path "*/node_modules/*" -not -path "*/.venv/*" | sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -20

# declared responsibilities — cheapest source of truth
head -12 <pkg>/__init__.py

# entry points and configuration surfaces
ls */ | head -40
ls **/config/*.yaml 2>/dev/null | wc -l

# static dependency direction
rg -n "^from <pkg>\.|^import <pkg>\." --type <lang> | head -40
```

### Limited exceptions

Reading function implementations is out of scope. To confirm an entry point, an export, a registration, or a module's stated purpose, a few **structural** fragments are allowed — `if __name__ == "__main__"`, `__all__`, decorator registration lines, module docstrings. Do not follow those fragments into business logic.

When static evidence is insufficient, write "未能从静态结构确认" rather than widening the scan into a deep code audit.

## Output: four fixed sections

Target **1–2 pages** of Markdown. A large repository may run longer, but raise the level of summarization instead of adding sections. Every line must serve overall structural understanding.

```markdown
# 工程结构地图：<项目名>

## 1. 工程概览
<one sentence: project type, language/stack, overall organization>
<main directory size distribution, with the counting rule stated>

## 2. 模块地图
<trimmed directory tree: path + one-line responsibility>

## 3. 结构关系
<main static dependency directions; confirmed boundaries; unknown items>

## 4. 组织惯例
<configuration layering; main extension pattern; how similar components are grouped>
```

This is an output constraint, not a questionnaire to fill item by item. Omit a subsection when it has no value or no evidence.

### Section guidance

**1. 工程概览** — one sentence on project type, language/stack, and overall organization, based on visible evidence. List the size distribution of the main directories only; state the counting rule, for example "仅统计源码文件，排除生成目录".

**2. 模块地图** — a trimmed tree showing main modules with a one-line responsibility each. Expand to the depth that distinguishes responsibilities; do not fix a layer count. List only modules that help overall understanding; merge minor directories. When a responsibility lacks evidence, use conservative wording rather than interpreting a name.

**3. 结构关系** — present observable static dependency directions with simple arrows or a small diagram. Describe confirmed package-level interfaces, internal modules, and layering boundaries. **Observing `A` imports `B` does not mean the architecture forbids the reverse.** Write a normative claim such as "禁止反向依赖" only when the repository carries explicit evidence. Never present a static import graph as a runtime call graph or a change-impact graph.

**4. 组织惯例** — where configuration lives and whether it is layered; the common extension organization (adapter, registry, plugin, inheritance) only when evidenced; how similar files are grouped and how tests are organized, in a few sentences. Do not output "新增某功能请修改 X/Y/Z 文件".

## Accuracy discipline

Classify internally, without labelling every sentence:

- **Fact** — paths, file counts, explicit exports, searchable imports, responsibilities stated in documentation.
- **Generalization** — a convention inferred from several directories or similar files.
- **Unknown** — a responsibility, public API boundary, or dependency constraint lacking static evidence.

Attach a qualifier only where a wrong reading would mislead: "从静态引用看", "按现有目录惯例", "未确认". Do not build an evidence-grade appendix.

## Content filter

Include a line only when it directly helps understand the overall organization. Prefer deleting:

- per-file listings and trivial directory depth;
- function and class method details;
- long dependency lists and low-value statistics;
- build, deploy, and CI tutorials;
- development steps, reading plans, quality advice, and task reasoning.

Internal scanning may be slightly deeper than the report. Never paste the scan log into the document.

## Delivery and side effects

- Default: output Markdown in the conversation. Create no repository file.
- When the user explicitly asks to save: write a `.md` file to the location they name. If they name none, ask first; do not write into the repository on your own initiative.
- Never write `.vibe/progress.md`, `docs/`, or any project memory file by default.
- Read-only throughout. Do not execute, modify, or install anything. When permissions or tooling block the scan, state the limit instead of widening the operation.

## Acceptance standard

Validate on an unfamiliar repository of 200+ files:

| Dimension | Question |
|---|---|
| Big picture | Can the user quickly name the main modules, their responsibilities, and their relationships? |
| Conciseness | Is the report about 1–2 pages with no irrelevant detail? |
| Accuracy | Are guesses never presented as facts, and static imports never presented as architectural rules? |
| Boundary | Is there no business teaching, implementation steps, or quality judgement? |
| Low cost | Does it rely mainly on directories, declarations, and static references rather than reading every file? |
| No side effects | Was nothing run, modified, or written without being asked? |

Efficiency target: about 20 minutes for an ordinary 200+ file repository. This is a design target to be measured, not a guarantee for every repository. A repository with ~1100 source files still calls for limited scanning and compression, not full reading.

## V2 operating rules

- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- Report confirmed facts, assumptions, verification performed, and material limitations.
