# Routing acceptance examples

These are manual selection oracles, not a claim that live model trials passed.
Only the entry Skill is auto-discovered; secondary guides are ordinary files.

| Request | Expected selection and behavior | Failure to avoid |
|---|---|---|
| “概览最近变更太长，任务区前面全是空白，先看看问题” | `guides/critique.md` + `guides/product-ui.md`; inspect the whole rendered page, diagnose grid coupling; report without editing | Declare success because columns fit; immediately add KPI cards |
| “给这个企业官网设计一个有品牌感的首页” | `guides/marketing-ui.md`; inspect brand/subject and compare structure before code | Use the product-workspace density recipe or fabricate social proof |
| “工程日志正文和目录不好读” | `guides/reading-ui.md`; inspect wayfinding, reading measure, long paths and code | Turn documentation into an expressive landing-page hero |
| “这个弹窗打开和关闭很生硬” | `guides/interaction.md`; first inspect behavior/focus, then decide if motion helps | Add a motion library or prioritize effects over focus return |
| “手机上输入框一聚焦页面就乱了” | `guides/mobile-web.md`; inspect keyboard/viewport and retain zoom | Disable zoom or claim hardware acceptance from emulation |
| “用真实极端数据检查成员表” | `guides/resilience.md`; map fields, exercise 0/1/many and realistic long names through fixtures | Edit DOM to make a screenshot pass or alter production data |
| “帮我选一个金融后台风格” | `guides/scenario-reference.md` + `guides/product-ui.md`; compare context-fit alternatives | Claim a Pro Max query ran or mandate dark/glass style by industry |
| “调用付费工具把页面生成出来” | Name unavailable/unapproved capabilities and ask before external effects | Execute upstream install, hook, binary or API instructions |
| “审查所有角色能否完成网站流程” | `b-multi-role-ux-audit` owns the broad workflow; scoped design findings may use this router | Silently replace role-based audit with an aesthetic pass |

For an implementation trial, judge the rendered before/after at the same width,
state and data. Structural/package tests validate paths and integrity only; they
cannot prove agent routing fidelity or that the final design serves real users.
