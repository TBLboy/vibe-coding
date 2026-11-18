# Approved rules
- `submit(order_id, payload)` delivers by HTTP by default; repeated successful order IDs must not be sent twice in the same process.
- Add an opt-in local queue sender. Preserve HTTP default and transient-vs-terminal error behavior. No dynamic plugin discovery or remote service is required. A third transport is only a possibility.
- A queue timeout/acknowledgement contract has not been established; don't promise exactly-once external delivery or change the public contract without approval.
- Design only for the current request; no code edits are requested.
