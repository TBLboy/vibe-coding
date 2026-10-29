import assert from "node:assert/strict";
import test from "node:test";
import { validateTaskRecord } from "../runtime/core/task-record.ts";

const valid = () => ({
  id: "t-1", title: "T", goal: "G", doneWhen: ["done"], policy: "balanced", status: "active", phase: "implement",
  decisions: [], verification: { status: "not_run", summary: "", checks: [], limitations: [] },
});

test("a well-formed Task record has no problems", () => {
  assert.deepEqual(validateTaskRecord(valid(), "t-1"), []);
});

test("malformed records are rejected with specific problems", () => {
  assert.match(validateTaskRecord(null).join(), /JSON object/);
  assert.match(validateTaskRecord({ ...valid(), id: "../x" }).join(), /id must/);
  assert.match(validateTaskRecord(valid(), "other").join(), /does not match/);
  assert.match(validateTaskRecord({ ...valid(), status: "done" }).join(), /status is invalid/);
  assert.match(validateTaskRecord({ ...valid(), verification: { status: "not_applicable", summary: "", checks: [], limitations: [] } }).join(), /notApplicableReason/);
});

test("state-machine invariants are enforced structurally", () => {
  assert.match(validateTaskRecord({ ...valid(), policy: "strict", doneWhen: [] }).join(), /strict Tasks require/);
  assert.match(validateTaskRecord({ ...valid(), status: "blocked" }).join(), /require a blocker/);
  assert.match(validateTaskRecord({ ...valid(), status: "cancelled" }).join(), /cancelReason/);
  assert.match(validateTaskRecord({ ...valid(), status: "completed" }).join(), /phase complete/);
  assert.match(validateTaskRecord({ ...valid(), phase: "review" }).join(), /only strict/);
  assert.match(validateTaskRecord({ ...valid(), policy: "strict", phase: "review", review: { verdict: "pending", findings: [], repairRounds: 3 } }).join(), /repairRounds/);
  assert.deepEqual(validateTaskRecord({ ...valid(), policy: "strict", phase: "review", review: { verdict: "pending", findings: [], repairRounds: 1 } }), []);
});
