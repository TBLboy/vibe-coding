# Approved rules
- `evaluate(value, strategy=None)` uses the legacy strategy by default. Legacy clamps negative values to zero; non-numeric values raise ValueError. The public `legacy` function stays importable.
- Add opt-in strategy `double`: clamp negatives to zero, then multiply by two; same invalid-input behavior. Unknown strategies raise ValueError.
- No change to legacy defaults/public import, no new dependencies. Existing uncommitted user edits must be preserved.
