---
name: b-opencode-model-config
description: Configure context window size and image input support for models of an existing OpenCode provider in opencode.json. Use when the user wants to change a model's context size, enable or disable image/vision input, fix models that reject attachments, or clean up deprecated model capability flags. Defaults to 500000 context and text+image input.
license: MIT
compatibility: opencode
metadata:
  type: tooling-skill-pack
  output: verified-model-capability-config
---

# OpenCode Model Configuration

## Use

Use when adjusting **capability declarations of models under an existing provider** in `opencode.json`:

- context window size (`limit.context`)
- image / vision input support (`modalities.input`)

Out of scope: adding a new provider, credentials and `baseURL`, picking which model to use, agent or permission settings. This Skill never invents a provider.

## Config contract

```json
"provider": {
  "<provider-id>": {
    "models": {
      "<model-id>": {
        "limit":      { "context": 500000, "output": 32000 },
        "modalities": { "input": ["text", "image"], "output": ["text"] }
      }
    }
  }
}
```

Defaults for this Skill: **`context: 500000`** and **`input: ["text", "image"]`**.

Rules:

- `limit` requires **both** `context` and `output`; writing only `context` fails schema validation. Preserve the existing `output`, or use 32000.
- `modalities.input` accepts `text` / `image` / `audio` / `video` / `pdf`.
- **`attachment: true` is a dead legacy field.** OpenCode 2.x ignores it and logs `kind=unsupported action="omitted unsupported legacy setting"` on every start. Only `modalities` controls image input. Remove `attachment` whenever you touch a model.
- A missing `limit` means the model silently falls back to a default (commonly 200000), so "no error" does not mean "configured".

## Method

1. **Read effective state first**, not just the file — the file may contain fields the runtime drops:
   ```bash
   opencode api --standalone get /api/model
   ```
   Each entry exposes `providerID`, `limit`, and `capabilities.input`.
2. **Verify real capability before declaring it.** See the verification section. Never copy a vendor capability field without a probe.
3. **Apply** with `scripts/configure_models.py` (atomic write, preserves file permissions, refuses to touch unrelated keys).
4. **Verify** by re-reading `/api/model` and confirming `limit` and `capabilities.input` changed.
5. Report what was changed, what was already correct, and any model whose real capability is still unproven.

## Verify real capability, never trust metadata

A declaration must match what the backend actually accepts. The declaration alone changes nothing upstream:

- declaring `image` on a text-only model → the client accepts an attachment, then the request fails at the provider;
- omitting `image` on a vision model → the client refuses to attach images at all.

Gateway metadata is routinely wrong. In one audited gateway, 6 of 12 models supported vision but reported an empty capability field; trusting it would have left half the fleet misconfigured.

Probe with a **solid-colour PNG (64×64 or larger) in at least two colours** and require every answer to be correct. Three traps make a single probe misleading:

| Symptom | Wrong conclusion | Actual cause |
|---|---|---|
| Model describes an object that is not there | "vision works" | **Hallucination.** A 1×1 image carries no signal. Use a large solid colour and a multi-colour control. |
| Empty response content | "no vision support" | Reasoning tokens consumed the budget. Raise `max_tokens` to ~256 and retry. |
| HTTP error naming a protocol or endpoint | "no vision support" | **Protocol mismatch**, not capability. Anthropic-family models often require `/v1/messages` with `image` content blocks rather than OpenAI-style `/v1/chat/completions` with `image_url`. |

Only a model that names every control colour correctly counts as verified. Report anything else as unverified rather than guessing.

## Safety

- Back up only with `--backup`, and tell the user the backup holds the API key in plain text; delete it once verified.
- Never print `apiKey` into transcripts, logs, or notes.
- Changing shared model capability declarations is a B-level decision: record it. Editing another user's or a team's config is C-level.

## Script

```bash
scripts/configure_models.py --provider <id>                       # defaults: 500000 context, text+image
scripts/configure_models.py --provider <id> --dry-run             # preview only
scripts/configure_models.py --provider <id> --model <m> --no-image
scripts/configure_models.py --provider <id> --context 200000 --keep-modalities
```

Resolves `$OPENCODE_CONFIG_DIR` then `~/.config/opencode/opencode.json`, or takes `--config`. It aborts if any key outside `limit` / `modalities` / `attachment` would change, and is idempotent — a second run reports no changes.

## Example

Request: "set every llmcenter model to 500k context and enable image input."

1. `/api/model` → 12 models at `context: 200000`, 6 with `input: ['text']`.
2. Gateway metadata flags only 6 as image-capable; probing the other 6 with red/green/blue PNGs shows all 6 answer correctly — 2 needed the Anthropic endpoint, 1 needed a larger `max_tokens`. All 12 are vision-capable.
3. `configure_models.py --provider llmcenter` → 12 models updated, 6 deprecated `attachment` flags removed.
4. `/api/model` → all 12 report `context: 500000` and `input: ['text','image']`; startup capability warnings stop.
