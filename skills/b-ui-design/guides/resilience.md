# UI resilience — realistic worst-case data

Adapted from Emil Kowalski's Break UI (MIT), pinned in `../SOURCES.md`.
This self-contained guide replaces its external catalog and mandatory fixture UI.

## Map before testing

List rendered fields and collections, their source, optionality, real validation
limits and current presentation. Include counts, timestamps, scope paths, status
labels, avatars, action labels and the length of lists. “No limit found” is a gap,
not permission to invent an arbitrary product limit.

Use plausible examples or schema-backed boundaries, not walls of random characters.
Test through the real mock/fixture/props boundary in an isolated development state.
Do not hand-edit the component's DOM/CSS to manufacture success, mutate production
data, or ship fixture selectors without a separate need.

## Self-contained case catalog

| Data | Cases and observations |
|---|---|
| Names/titles | A short name such as Jo; a realistic compound name; long CJK task title; natural wrapping, no orphaned metadata or crushed avatar |
| Identifiers | Long repository path, email or URL without spaces; no page-level overflow, full value available when truncated |
| Optional fields | Missing avatar, holder, reason or timestamp; no broken image, empty separator or invented status |
| Counts | 0, 1, realistic large count; correct labels, number formatting, stable badge/controls |
| Collections | Empty, one item, many realistic items; unequal status group sizes and 2 members next to 30 history entries |
| Time/status | Old dates, absent date, longer translated status; sensible placement and explicit state meaning |
| Content detail | Long scope list or abandonment reason beside short tasks; comparison remains legible without equal-height card padding |
| Environment | Narrow container as actually used, 320px page where supported, desktop, enlarged text; dark/RTL only when supported |

Spread cases across realistic rows rather than stacking every extreme in one
record. Compare at the true container width: a sidebar is not a full-width page.
For growing collections consider the existing pagination/disclosure contract;
do not add virtualization, filters or count caps merely to hide a layout defect.

## Look for failure signatures

Crushed fixed-size icons suggest flex shrinking; text escaping its cell suggests
missing shrink/wrap allowance; displaced controls suggest missing overflow policy.
Large blank regions may come from grid row coupling to a longer neighbor. Lost
row comparison may require a list/table rather than more boxes. These are
hypotheses: confirm against rendered geometry and actual behavior.

Report each defect with value, container/width, observed consequence and candidate
fix. Separate broken, visually awkward and fragile/inferred findings. Ask for
product decisions such as hiding essential data; do not silently truncate it.
For requested fixes, rerun the same cases and retained normal data. State which
states were rendered and which remain untested.
