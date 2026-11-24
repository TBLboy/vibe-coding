# Product UI — operational clarity

Adapted from Dammyjay93's Interface Design (MIT) and Impeccable's Operate mode
(Apache-2.0); exact snapshots and notices are in `../SOURCES.md`. This guide is
self-contained; upstream setup, persistence and tool instructions are not used.

## Intent before composition

Name the actual person and the verb: locate a broken deployment, understand team
progress, approve an application. “A modern dashboard” is not a job. Identify the
information needed first and what can wait. Preserve existing vocabulary, navigation,
role limits and design tokens. Familiar, efficient conventions are valid; novelty
is not a reason to replace a working interaction.

## Choose the representation from the reading task

- **Table:** compare repeated structured fields across records; aligned columns
  beat separate boxes when users scan owners, statuses and dates.
- **List:** read titles with variable secondary detail; keep metadata positions
  predictable, allow natural wrapping instead of forcing identical heights.
- **Board:** reason about stages or workflow distribution. Use only when that job
  matters; read-only boards are possible but must not imply dragging or editing.
- **Timeline:** reconstruct chronology, with actor/action/time and meaningful links.
  Secondary history must not dominate the main work area just because it is longer.
- **Card:** an independent contained unit, action or comparison; not a mandatory
  wrapper around every task, metric, person or section.

Explain a tradeoff between at least two plausible structures for a substantial
redesign. Do not add filters, metrics, search, charts or bulk actions absent a real
need and authorization. A status count already shown elsewhere may add no value.

## Hierarchy and layout

Choose one focal work area. Supporting chrome and metadata should recede through
weight, tone and spacing, not unreadably faint text. Specify a coherent density
and repeat it; related facts sit closer than unrelated groups. Reuse project
type/spacing/radius/semantic-color tokens before adding any.

Proportions state relationships. Inspect both columns with realistic unequal data:
does a tall history feed create a dead zone and push a primary task below the fold?
Consider independent columns, bounded preview with explicit expansion, or moving
history after primary work. Choose based on task priority and keyboard/reading
order, not equal-height symmetry. Do not force a 2:1 ratio when content disproves it.

Use color for state/action, always with labels. Read-only content stays visibly
static. Identity can come through type, palette, density and precise details without
turning navigation into a themed prop. Do not imitate another product's brand.

## States and evidence

Retain loading, empty, failure/retry, role-denied and success behavior. Distinguish
“no tasks” from “no results” only when filtering actually exists. Keep factual data,
owner/holder distinctions, scope, timestamps and abandonment reasons available.

Inspect actual desktop and narrow layouts with 0/1/many members, unequal status
groups and long task names. Check whether primary work is discoverable without
scrolling past a secondary feed, whether columns align for comparison, and whether
non-interactive rows falsely look actionable. Verify real keyboard paths and error
states. Record concrete defects, not “looks polished” as a substitute for evidence.
