# Scoped critique and refinement

Adapted from Impeccable (Apache-2.0); pinned snapshots in `../SOURCES.md`.
The main Agent performs this method; no upstream launcher, scoring service,
subagent, state directory or automatic fixing workflow is involved.

## Establish authority and scope

Separate refinement (retain identity) from redesign (replace a visual direction
within product constraints). Identify the user task, requested target and retained
contracts before judging taste. A question asking whether something is good is
report-only. An explicit “fix” authorizes only the requested scope. A whole-site multi-role workflow audit is outside this guide; use scoped business-flow verification rather than substituting visual critique.

## Look, then reason

Inspect a rendered baseline at actual size where tooling permits. If it cannot
run, use supplied screenshots and source while clearly limiting conclusions.
Do not mark a rendered issue passed or failed from source alone. Identify:

1. The first thing the eye notices and whether it is the primary task.
2. Reading/scan order, grouping, alignment and consistency of comparisons.
3. Density, vertical rhythm, negative space and whether secondary content pushes
   primary content away. Check the full page, not just each component in isolation.
4. Visual signifiers versus actual capabilities: links, buttons, static content,
   selected state, draggable appearance and read-only restrictions.
5. Relevant loading/empty/error/success/focus/overflow states and narrow reflow.

## Diagnose instead of decorating

Rank findings by user impact. For each, give location, observation, consequence,
and a concrete fix tied to the user task. Distinguish functional defects from
visual hierarchy problems and subjective alternatives. Avoid numeric aesthetic
scores without a real oracle.

Work in order: remove unsupported or duplicated furniture; reduce competing
emphasis; reconcile with existing tokens; only then restyle. Do not solve a
structural gap by adding a KPI strip, hero, illustration or extra card without a
need. Unequal card height is not inherently a defect; the lost comparison or scan
path is what needs evidence. Whitespace is valid when it protects a task, not when
an unrelated grid row forces a void.

## Verify the fix

For authorized edits, retain a before/after comparison of the whole surface at
the same widths and state. Confirm the original defect is gone and nearby behavior
is retained. Exercise the affected actions/keyboard paths. Inspect all changes
from one pass before taking another screenshot; a capture alone is not critique.
State remaining limitations and prioritize unresolved findings. Do not claim
accessibility compliance or performance targets without appropriate checks.
