import assert from "node:assert/strict";
import test from "node:test";
import { DEFAULT_SYNC_INTERVAL_MS, resolveSyncInterval, startPeriodicSync } from "../runtime/opencode/plugins/vibe-v2/team/periodic-sync.ts";

test("background sync interval defaults to 10s and is configurable", () => {
  assert.equal(DEFAULT_SYNC_INTERVAL_MS,10_000);
  assert.equal(resolveSyncInterval(undefined),10_000);
  assert.equal(resolveSyncInterval("30000"),30_000);
  assert.equal(resolveSyncInterval("0"),0,"0 disables background sync");
  for(const bad of ["","-1","abc","1.5","  "]) assert.equal(resolveSyncInterval(bad),10_000,bad);
});

test("disabled or zero interval registers no timer", async () => {
  let calls=0;
  const stop=startPeriodicSync({intervalMs:0,sync:async()=>{calls++;}});
  assert.equal(typeof stop,"function");
  await new Promise(r=>setTimeout(r,30));
  stop();
  assert.equal(calls,0);
});

test("periodic sync runs repeatedly and stops cleanly", async () => {
  let calls=0;
  const stop=startPeriodicSync({intervalMs:10,sync:async()=>{calls++;}});
  await new Promise(r=>setTimeout(r,60));
  stop();
  const seen=calls;
  assert.ok(seen>=2,"expected repeated background syncs");
  await new Promise(r=>setTimeout(r,40));
  assert.equal(calls,seen,"no sync after stop");
});

test("a slow sync never overlaps the next tick", async () => {
  let running=0,maxRunning=0,calls=0;
  const stop=startPeriodicSync({intervalMs:5,sync:async()=>{
    calls++;running++;maxRunning=Math.max(maxRunning,running);
    await new Promise(r=>setTimeout(r,25));running--;
  }});
  await new Promise(r=>setTimeout(r,90));
  stop();
  assert.ok(calls>=1);
  assert.equal(maxRunning,1,"background sync must be serialized");
});

test("a failing sync is reported and does not stop later ticks", async () => {
  const errors:unknown[]=[];let calls=0;
  const stop=startPeriodicSync({intervalMs:10,sync:async()=>{calls++;throw new Error("busy");},onError:e=>errors.push(e)});
  await new Promise(r=>setTimeout(r,55));
  stop();
  assert.ok(calls>=2,"failures must not cancel the timer");
  assert.equal(errors.length,calls);
});

test("a throwing onError does not break the timer", async () => {
  let calls=0;
  const stop=startPeriodicSync({intervalMs:10,sync:async()=>{calls++;throw new Error("x");},onError:()=>{throw new Error("diagnostics failed");}});
  await new Promise(r=>setTimeout(r,50));
  stop();
  assert.ok(calls>=2);
});
