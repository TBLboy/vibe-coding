# 当前需求摘要

- 当前目标：将项目初始化流程固化为 a-project-init skill（.project-log 现有链路 + AGENTS.md 建立/安全注入 + 路由）
- 当前基线：需求基线暂未单独建立，以业务原子 BL-PROJECT-INIT-001..004 为事实源
- 范围内：项目初始化编排、AGENTS.md 通用区与项目级区、幂等安全注入、通用规则模板资产化、skill 路由
- 范围外：修改 init_project.py 与 project-log-template、子文件夹 AGENTS.md 处理、AGENTS.md 内容自动改写
- 关键约束：.project-log 走现有链路不改动；已有 AGENTS.md 一字不动；重复初始化幂等；模板存于 skill 内部为唯一来源
- 阻塞问题：无

机器可读事实源：`.project-log/requirements/baseline.yaml` 与 `.project-log/business-logic/atoms.yaml`。
