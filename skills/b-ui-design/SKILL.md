---
name: b-ui-design
description: "网页设计/UI设计/UX设计/视觉优化/交互优化/界面改版 | Route web and UI design, redesign and scoped critique to curated product, marketing, reading, interaction, mobile and resilience guides."
license: MIT
compatibility: opencode
metadata:
  v2: true
---

# UI Design Router

## Boundary and inputs

This domain (`b-*`) Skill selects specialist guidance; it does not prescribe a
technology stack or a universal visual style. Automatic activation is appropriate
for an explicit UI-design request because selecting and reading a guide is cheap
and read-only. It does not authorize implementation, a whole-site audit, publishing,
installation or paid services beyond the user's request.

Identify the actual surface, user job, requested operation (plan/build/refine/
critique), scope, existing design system and technical constraints. Inspect the
target before choosing a route. Ask one focused question only if missing context
materially changes that choice. Preserve the project's stack; do not assume React,
Tailwind, a native app, or the framework author's current project.

## Secondary routing

Paths below are relative to this Skill directory. Read **one primary guide** and
only the supplements needed by the target; do not load the whole bundle.

| Surface or intent | Primary guide | Appropriate supplement |
|---|---|---|
| Workspace, SaaS app, admin, developer tool, dense operational data | [Product UI](guides/product-ui.md) | Interaction for controls; resilience for unequal/large data |
| Company site, brand/launch page, landing page, visual identity | [Marketing UI](guides/marketing-ui.md) | Scenario reference for alternatives, not a preset verdict |
| Documentation, engineering log, article, help, knowledge base | [Reading UI](guides/reading-ui.md) | Mobile or resilience for code/tables/long paths |
| Existing screen: diagnose hierarchy, awkward layout, visual clutter, “too ugly” | [Critique and refinement](guides/critique.md) | The matching surface guide; diagnose before restyling |
| Component feedback, button/popover, motion or interaction detail | [Interaction craft](guides/interaction.md) | Mobile only for touch/platform behavior |
| Mobile Web/PWA, touch, viewport, scroll, safe area | [Mobile Web](guides/mobile-web.md) | Existing surface guide; not a native-app recipe |
| Long/missing text, 0/1/many items, unequal panels, realistic worst cases | [UI resilience](guides/resilience.md) | The affected surface guide |
| Industry/platform/style alternatives, palette or pattern selection | [Scenario reference](guides/scenario-reference.md) | Select the actual surface owner before implementation |

Surface and style are separate: a software company's homepage is marketing, its
workspace is product UI, its docs are reading UI. Style cannot redefine the user
job. An explicit existing design/Figma source takes precedence over free direction.
Unsupported specialties (e.g. native mobile, checkout research) require named gaps,
not a claim that a generic guide fully covers them.

## Selection and precedence

State the selected path and why it fits in one sentence. Prefer one primary owner
over stacking conflicting philosophies. User/project contracts and accessibility
requirements outrank guide preferences; surface guidance outranks style suggestions.
If a material conflict remains, name it and ask before changing product semantics.

The guides are self-contained adaptations of the pinned public material recorded
in [SOURCES.md](SOURCES.md). `sources/` is a provenance-only snapshot collection,
not another set of executable Skills. Do not follow its unresolved links, commands,
hooks, binary downloads, installers, independent state files or delegation rules.
No upstream script, remote asset, service, font or dependency is authorized here.
Nested sources are intentionally not auto-discovered as independent Skills.

For a multi-role, whole-running-application audit, use `b-multi-role-ux-audit`;
this route owns scoped design judgment, not a replacement audit workflow. Engineering
implementation and structured verification remain with `a-engineering-landing`
and `a-verification` when useful; the main Agent retains lifecycle ownership.

## Output and completion

Return only what the operation needs: selected guide(s), user job and retained
constraints, compact design rationale/alternatives, concrete findings or approved
changes, and relevant verification evidence or gaps. A critique question alone is
report-only. Planning does not imply permission to edit.

Selection is complete when the surface and guide ownership are clear. A design
plan needs inspectable layout reasoning before code. Implementation needs real
rendered inspection at representative widths, relevant interaction/state checks,
and honest limitations; merely taking a screenshot is not visual acceptance.
Do not call source inventory tests proof of design quality.

## V2 operating rules

- For registered Tasks, use Runtime lifecycle events in `docs/03-STATE-MACHINE.md`; never edit Task JSON directly.
- Follow the current project `AGENTS.md` and Session policy.
- Use a persistent `.vibe/tasks/<task-id>.json` only when V2 Task policy warrants it.
- Write `.vibe/sessions/<session-id>/current-session.md` only for resumable unfinished work or a blocker.
- Update `.vibe/progress.md` only for durable project facts.
- Use only the V2 Task JSON and V2 Project Memory locations described above for durable state.
- The main Agent alone owns strict review; no guide delegates to another Agent.
- Report confirmed facts, assumptions, verification performed, and material limitations.
