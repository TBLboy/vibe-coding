import assert from "node:assert/strict";
import test from "node:test";
import { buildModeCommandPrompt, isMode, isPendingModeChange, modeStorageKey, normalizeMode, pendingModeStorageKey, renderModeInstructions } from "../runtime/core/mode.ts";

test("only the three declared modes are valid", () => {
  assert.equal(isMode("fast"), true);
  assert.equal(isMode("balanced"), true);
  assert.equal(isMode("strict"), true);
  assert.equal(isMode("quick"), false);
  assert.equal(isMode("STRICT"), false);
});

test("missing or invalid stored mode defaults to balanced", () => {
  assert.equal(normalizeMode(undefined), "balanced");
  assert.equal(normalizeMode("old-mode"), "balanced");
  assert.equal(normalizeMode("strict"), "strict");
});

test("mode storage key is scoped by Session ID", () => {
  assert.notEqual(modeStorageKey("session-a"), modeStorageKey("session-b"));
  assert.notEqual(pendingModeStorageKey("session-a", "token"), pendingModeStorageKey("session-b", "token"));
  assert.throws(() => modeStorageKey("  "), /sessionID/);
  assert.throws(() => pendingModeStorageKey("session-a", " "), /token/);
});

test("bare mode command asks for acknowledgement only", () => {
  const prompt = buildModeCommandPrompt("fast", "  ", false, "token-123");
  assert.match(prompt, /invoked \/fast/);
  assert.match(prompt, /vibe_set_session_mode/);
  assert.match(prompt, /token-123/);
  assert.match(prompt, /do not start implementation/);
  assert.doesNotMatch(prompt, /After the tool succeeds, execute the following user request/);
});

test("mode command with attachments and no text treats attachments as task input", () => {
  const prompt = buildModeCommandPrompt("balanced", "", true, "token-123");
  assert.match(prompt, /attachments as the task input/);
  assert.doesNotMatch(prompt, /do not start implementation/);
});

test("mode command with task text preserves the task", () => {
  const prompt = buildModeCommandPrompt("strict", "  change the schema  ", false, "token-456");
  assert.match(prompt, /After the tool succeeds, execute the following user request/);
  assert.match(prompt, /change the schema/);
  assert.match(prompt, /frozen policy/);
});

test("only an unused matching pending token can authorize a mode change", () => {
  assert.equal(isPendingModeChange({ mode: "strict", token: "abc", consumed: false }, "strict", "abc"), true);
  assert.equal(isPendingModeChange({ mode: "strict", token: "abc", consumed: true }, "strict", "abc"), false);
  assert.equal(isPendingModeChange({ mode: "fast", token: "abc", consumed: false }, "strict", "abc"), false);
  assert.equal(isPendingModeChange(undefined, "strict", "abc"), false);
});

test("mode policy does not expose reviewer in fast or balanced", () => {
  assert.match(renderModeInstructions("fast"), /Do not invoke the reviewer/);
  assert.match(renderModeInstructions("balanced"), /Do not invoke the reviewer/);
  assert.match(renderModeInstructions("strict"), /reviewer returns go/);
});

test("strict instructions treat background launch as pending without inventing tool parameters", () => {
  const text = renderModeInstructions("strict");
  assert.match(text, /running result is only a launch/);
  assert.match(text, /without polling/);
  assert.match(text, /natural parent continuation/);
  assert.match(text, /Do not invent a foreground option/);
  assert.doesNotMatch(text, /fresh foreground|background=false|background:false/);
});

test("Session context carries the absolute memory root and the registered Task", () => {
  const text = renderModeInstructions("balanced", "ses_a", { memoryRoot: "/proj", activeTask: { taskID: "t1", policy: "strict", active: false } });
  assert.match(text, /Project memory root: \/proj/);
  assert.match(text, /Never create another \.vibe\//);
  assert.match(text, /Registered Task for this Session: t1 \(frozen policy strict, paused\/closed\)/);
  assert.match(text, /Session recovery file: \/proj\/\.vibe\/sessions\/ses_a\/current-session\.md/);
  assert.match(renderModeInstructions("fast"), /No Task is registered/);
});


test("compact context distinguishes new work from a differently frozen Task", () => {
  for (const mode of ["fast", "balanced", "strict"] as const) {
    for (const frozen of ["fast", "balanced", "strict"] as const) {
      for (const active of [true, false]) {
        const facts = { memoryRoot: "/proj with space", activeTask: { taskID: "t1", policy: frozen, active } };
        const text = renderModeInstructions(mode, "session/one", facts);
        assert.equal(text, renderModeInstructions(mode, "session/one", facts));
        assert.ok(text.includes(`New-work policy (${mode}):`));
        assert.ok(text.includes(`frozen policy ${frozen}, ${active ? "active" : "paused/closed"}`));
        assert.ok(text.includes("Session recovery file: /proj with space/.vibe/sessions/session%2Fone/current-session.md"));
        assert.ok(text.includes("vibe-reviewer follows its read-only strict review contract"));
        assert.ok(text.includes("never edit directly"));
        assert.ok(text.includes("do not register it again"));
        if (mode !== frozen) {
          assert.ok(text.includes(`Only if continuing that existing Task, apply frozen policy (${frozen}):`));
          assert.doesNotMatch(text.split("Only if continuing that existing Task")[1], /Always create\/register|action=start/);
        } else {
          assert.ok(!text.includes("Only if continuing that existing Task"));
        }
        assert.equal(text.includes("reviewer returns go"), mode === "strict" || frozen === "strict");
      }
    }
  }
});

test("mode experience instructions distinguish consultation, tracking and risk without weakening review", () => {
  for (const mode of ["fast", "balanced", "strict"] as const) {
    const text = renderModeInstructions(mode);
    assert.match(text, /Ordinary consultation\/read-only explanation or investigation without durable tracking needs creates no Task or Reviewer call in any mode/);
    assert.match(text, /Stop before strict-risk implementation under fast\/balanced policy; require explicit \/strict and a new strict Task/);
    assert.match(text, /not file count/);
  }
  assert.match(renderModeInstructions("fast"), /even for clear multi-file work/);
  assert.match(renderModeInstructions("balanced"), /direct for simple work/);
  assert.match(renderModeInstructions("strict"), /implementation \(even small\)/);
  assert.match(renderModeInstructions("strict"), /no mandatory separate documents or Skill sequence/);
  assert.match(renderModeInstructions("strict"), /reviewer returns go/);
});

test("mode switch prompt uses returned frozen policy and never resumes a pointer automatically", () => {
  const prompt = buildModeCommandPrompt("fast", "", false, "token");
  assert.match(prompt, /if its result reports a different frozen Task policy/);
  assert.match(prompt, /Do not imply a paused\/closed Task is active or resume it automatically/);
  assert.match(prompt, /do not start implementation/);
});
