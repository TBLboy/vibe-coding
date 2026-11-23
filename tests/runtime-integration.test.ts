import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, writeFile, readFile, rm, realpath } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { setup } from "../runtime/opencode/plugins/vibe-v2/setup.ts";
import type { HostContext, ToolDefinition, CommandDefinition, PermissionEvent, JsonValue, ToolAfterEvent } from "../runtime/opencode/plugins/vibe-v2/host-contract.ts";
import { createTask, type Task } from "../runtime/core/task-machine.ts";
import { modeStorageKey } from "../runtime/core/mode.ts";

async function harness(t: { after(fn: () => Promise<void>): void }) {
  const base = await realpath(await mkdtemp(resolve(tmpdir(), "vibe-runtime-")));
  t.after(() => rm(base, { recursive: true, force: true }));
  const root = resolve(base, "project");
  await mkdir(resolve(root, ".vibe/tasks"), { recursive: true });
  await writeFile(resolve(root, "src.txt"), "A");
  const records = new Map<string, JsonValue>();
  const tools = new Map<string, ToolDefinition>(); const commands = new Map<string, CommandDefinition>();
  const sessions = new Map<string, { directory: string; parentID?: string; agent?: string; outcome?: string }>([["main", { directory: root }], ["other", { directory: root }], ["review", { directory: root, parentID: "main", agent: "vibe-reviewer" }], ["wrong", { directory: root, parentID: "other", agent: "vibe-reviewer" }]]);
  const transcripts = new Map<string, unknown[]>();
  let after!: (event: ToolAfterEvent) => Promise<void>;
  let callNumber=0;
  let permission!: (event: PermissionEvent) => Promise<void>;
  let contextHook!: (event: { sessionID: string; system: { type: "text"; text: string }[] }) => Promise<void>;
  let queued: unknown;
  const ctx: HostContext = {
    storage: { get: async k => structuredClone(records.get(k)), set: async (k,v) => { records.set(k, structuredClone(v)); }, remove: async k => { records.delete(k); } },
    command: { transform: async fn => fn({ add: d => { commands.set(d.name,d); } }) },
    tool: { transform: async fn => fn({ add: d => { tools.set(d.name,d); } }), hook: async (_,fn) => { after=fn; } },
    session: { get: async ({sessionID}) => sessions.get(sessionID), context: async ({sessionID}) => structuredClone(transcripts.get(sessionID) ?? []), prompt: async p => { queued = p; }, hook: async (_, fn) => { contextHook = fn; } },
    permission: { hook: async (_, fn) => { permission = fn; } },
  };
  await setup(ctx);
  const taskPath = resolve(root,".vibe/tasks/t1.json");
  const call = async (name: string, input: Record<string, unknown>, sessionID = "main", agent = "vibe-main") => (await tools.get(name)!.execute(input,{sessionID,agent})).content;
  const ctl = (action: string, event?: Record<string, unknown>, session = "main") => call("vibe_task_control",{action,taskID:"t1",...(event ? {event} : {})},session);
  const step = (type: string, args: Record<string, unknown> = {}, session = "main") => ctl("transition",{type,...args},session);
  const read = async () => JSON.parse(await readFile(taskPath,"utf8")) as Task;
  const write = (task: Task) => writeFile(taskPath,JSON.stringify(task,null,2)+"\n");
  const fresh = async (policy: Task["policy"] = "strict") => { records.set(modeStorageKey("main"),policy); await write(createTask({id:"t1",title:"Task",goal:"G",doneWhen:["A"],policy})); };
  const permit = async (sessionID = "main", agent = "vibe-main", id = `call-${++callNumber}`) => { const e: PermissionEvent = {sessionID,agent,action:"subagent",resources:["vibe-reviewer"],source:{type:"tool",messageID:"msg",id},effect:"allow"}; await permission(e); return {effect:e.effect,id}; };
  const ready = async () => { await fresh(); assert.match(await ctl("start"),/started/); assert.match(await step("begin_implementation",{risk:"strict"}),/implement/); assert.match(await step("begin_verification",{artifacts:["src.txt"]}),/verify/); assert.match(await step("verification_passed",{summary:"OK",checks:["test: passed"]}),/review/); };
  const authorize = async () => { const result=await ctl("authorize_review"); assert.match(result,/permit issued/); };
  const complete = async (id: string, session = "review", extra = {}, eventExtra = {}) => after({tool:"subagent",sessionID:"main",agent:"vibe-main",messageID:"msg",id,input:{agent:"vibe-reviewer",background:false},status:"completed",result:{output:{sessionID:session,status:"completed",output:JSON.stringify({verdict:"go",findings:[],requiresUserDecision:false,...extra})}},...eventExtra});
  const launch = async (id: string, session = "review", input: Record<string, unknown> = {agent:"vibe-reviewer"}, eventExtra = {}) => after({tool:"subagent",sessionID:"main",agent:"vibe-main",messageID:"msg",id,input,status:"completed",result:{output:{sessionID:session,status:"running",output:"Child is working"}},...eventExtra});
  const finished = (session = "review", extra = {}) => {
    sessions.set(session, {...sessions.get(session)!, outcome:"succeeded"});
    transcripts.set(session, [
      {type:"user", id:"msg_prompt", text:"Review the Task"},
      {type:"assistant", id:"msg_result", agent:"vibe-reviewer", finish:"stop", time:{created:1,completed:2}, content:[{type:"text",text:JSON.stringify({verdict:"go",findings:[],requiresUserDecision:false,...extra})}]},
      {type:"idle", id:"msg_idle", outcome:"succeeded"},
    ]);
  };
  return {base,root,ctx,records,tools,commands,sessions,transcripts,call,ctl,step,read,write,fresh,permit,ready,authorize,complete,launch,finished,queued:()=>queued, context:async(sessionID:string)=>{const e={sessionID,system:[] as {type:"text";text:string}[]};await contextHook(e);return e.system[0]?.text;}};
}

test("production setup: explicit mode command queues and consumes a session token", async t => {
  const h = await harness(t);
  assert.match(await h.context("main"),/Authoritative Session mode: balanced/);
  await h.commands.get("strict")!.execute({sessionID:"main",prompt:{text:"do it"}});
  const prompt = h.queued() as {text:string;delivery:string};
  assert.equal(prompt.delivery,"queue"); const token = prompt.text.match(/token=([\w-]+)/)![1];
  assert.match(await h.call("vibe_set_session_mode",{mode:"strict",token},"other"),/Rejected/);
  assert.match(await h.call("vibe_set_session_mode",{mode:"strict",token}),/changed/);
  assert.match(await h.call("vibe_set_session_mode",{mode:"strict",token}),/Rejected/);
  assert.match(await h.context("main"),/Authoritative Session mode: strict/);
  assert.match(await h.context("other"),/Authoritative Session mode: balanced/);
});

test("production lifecycle rejects skips, fabricated completion and direct edits", async t => {
  const h = await harness(t); await h.fresh();
  assert.match(await h.ctl("start"),/started/);
  assert.match(await h.step("verification_passed",{summary:"fake",checks:["fake"]}),/Rejected/);
  assert.match(await h.step("review_go"),/Rejected/);
  const original = await h.read(); await h.write({...original,phase:"review",review:{verdict:"pending",findings:[],repairRounds:0}});
  assert.match(await h.ctl("authorize_review"),/outside Runtime|requires sufficient verification/);
  await h.write(original);
  assert.match(await h.step("begin_implementation",{risk:"standard"}),/implement/);
  assert.match(await h.ctl("close"),/Rejected/);
});

test("strict permit admission never completes review; only correlated native completion closes", async t => {
  const h = await harness(t); await h.ready();
  assert.equal((await h.permit()).effect,"deny"); await h.authorize();
  await h.complete("fake"); assert.equal((await h.read()).review?.verdict,"pending");
  const admitted=await h.permit(); assert.equal(admitted.effect,"allow"); assert.equal((await h.permit()).effect,"deny");
  assert.equal((await h.read()).review?.verdict,"pending"); assert.match(await h.ctl("close"),/Rejected/);
  await h.complete(admitted.id,"wrong"); await h.complete("wrong"); await h.complete(admitted.id,"review",{},{status:"error"});
  await h.complete(admitted.id,"review",{},{input:{agent:"vibe-reviewer",background:true}});
  assert.equal((await h.read()).review?.verdict,"pending");
  await h.complete(admitted.id); assert.equal((await h.read()).review?.verdict,"go");
  await h.complete(admitted.id); assert.match(await h.ctl("close"),/closed/); assert.match(await h.ctl("resume"),/closed/);
});

test("evidence is captured before checks, invalidated after any covered edit, including after review", async t => {
  const h = await harness(t); await h.fresh(); await h.ctl("start"); await h.step("begin_implementation",{risk:"strict"}); await h.step("begin_verification",{artifacts:["src.txt"]});
  await writeFile(resolve(h.root,"src.txt"),"B");
  assert.match(await h.step("verification_passed",{summary:"stale",checks:["test"]}),/changed/);
  await h.step("invalidate_verification"); await h.step("begin_verification",{artifacts:["src.txt"]});
  assert.match(await h.step("verification_passed",{summary:"OK",checks:[]}),/nonempty/);
  await h.step("verification_passed",{summary:"OK",checks:["test"]}); await h.authorize(); const first=await h.permit();
  await writeFile(resolve(h.root,"src.txt"),"C"); await h.complete(first.id); assert.equal((await h.read()).review?.verdict,"pending");
  await h.step("invalidate_verification"); await h.step("begin_verification",{artifacts:["src.txt"]}); await h.step("verification_passed",{summary:"OK",checks:["test"]}); await h.authorize(); const second=await h.permit();
  await h.complete(first.id); assert.equal((await h.read()).review?.verdict,"pending"); await h.complete(second.id);
  await writeFile(resolve(h.root,"src.txt"),"D"); assert.match(await h.ctl("close"),/current verification/);
  assert.match(await h.step("invalidate_verification"),/implement/);
});

test("frozen policy across Session recovery and ownership handover", async t => {
  const h=await harness(t); await h.fresh(); await h.ctl("start"); const original=await h.read();
  await h.write({...original,policy:"balanced"}); assert.match(await h.ctl("resume",undefined,"other"),/outside Runtime|requires sufficient verification/);
  await h.write(original); assert.match(await h.ctl("resume",undefined,"other"),/frozen policy strict/);
  assert.match(await h.step("begin_implementation",{risk:"strict"}),/not active|outside Runtime/);
  assert.match(await h.step("begin_implementation",{risk:"strict"},"other"),/implement/);
  assert.equal((await h.read()).policy,"strict");
});

test("risk is a floor; nonstrict task cannot begin strict-risk implementation", async t => {
  const h=await harness(t); await h.fresh("balanced"); await h.ctl("start");
  assert.match(await h.step("begin_implementation",{risk:"strict"}),/explicit \/strict/);
  assert.equal((await h.read()).phase,"prepare");
  assert.match(await h.step("begin_implementation",{risk:"standard"}),/implement/);
  await h.step("begin_verification",{artifacts:["src.txt"]}); await h.step("verification_passed",{summary:"OK",checks:["test"]});
  assert.match(await h.ctl("close"),/closed/); assert.equal((await h.permit()).effect,"deny");
});

test("blocked review requires decision, repairs invalidate evidence, old tokens cannot replay", async t => {
  const h=await harness(t); await h.ready(); await h.authorize(); const first=await h.permit();
  const finding={severity:"major",requirement:"criterion",location:"src.txt",problem:"wrong",requiredChange:"fix"};
  await h.complete(first.id,"review",{verdict:"no-go",findings:[finding],requiresUserDecision:true}); assert.equal((await h.read()).status,"blocked");
  await h.ctl("pause"); assert.match(await h.ctl("resume_blocked",{phase:"implement"},"other"),/recorded decision/);
  assert.match(await h.ctl("resume_blocked",{phase:"implement",decision:"User approved repair"},"other"),/resumed/);
  assert.equal((await h.read()).verification.status,"not_run"); await h.complete(first.id); assert.equal((await h.read()).phase,"implement");
});

test("external Git worktree shares canonical memory, but evidence binds to its actual checkout", async t => {
  const h=await harness(t); const git=(...args:string[])=>execFileSync("git",["-C",h.root,...args],{stdio:"ignore"});
  git("init","-q"); git("add","src.txt"); git("-c","user.name=Test","-c","user.email=test@example.invalid","commit","-qm","base");
  const worktree=resolve(h.base,"linked"); git("worktree","add","-qb","test-worktree",worktree);
  h.sessions.set("main",{directory:worktree}); await h.fresh("balanced"); await h.ctl("start");
  await h.step("begin_implementation",{risk:"standard"}); await writeFile(resolve(worktree,"src.txt"),"B");
  await h.step("begin_verification",{artifacts:["src.txt"]});
  assert.equal((await h.read()).verification.evidence?.root,worktree);
  await writeFile(resolve(worktree,"new.txt"),"new untracked input");
  assert.match(await h.step("verification_passed",{summary:"OK",checks:["test"]}),/changed/);
  assert.equal(await readFile(resolve(h.root,"src.txt"),"utf8"),"A");
});

test("native background launch stays pending until successful child completion at parent context", async t => {
  const h = await harness(t); await h.ready(); await h.authorize(); const permit = await h.permit();
  await h.launch(permit.id);
  assert.equal((await h.read()).review?.verdict, "pending");
  await h.complete(permit.id); // A second tool payload cannot forward a verdict for a bound background child.
  assert.equal((await h.read()).review?.verdict, "pending");
  await h.context("main"); assert.equal((await h.read()).review?.verdict, "pending");
  assert.match(await h.ctl("close"), /Rejected/);
  h.finished();
  await h.context("other"); assert.equal((await h.read()).review?.verdict, "pending");
  await h.context("main");
  assert.equal((await h.read()).review?.verdict, "go");
  await h.context("main"); assert.match(await h.ctl("close"), /closed/);
});

test("only the admitted native call may bind a fresh background child", async t => {
  const h = await harness(t); await h.ready(); await h.authorize(); const permit = await h.permit();
  h.finished();
  await h.launch("unrelated"); await h.context("main");
  assert.equal((await h.read()).review?.verdict, "pending");
  await h.launch(permit.id, "wrong"); await h.context("main");
  await h.launch(permit.id, "review", {agent:"vibe-reviewer",sessionID:"review"});
  await h.launch(permit.id, "review", {agent:"other"});
  await h.launch(permit.id, "review", {agent:"vibe-reviewer"}, {status:"error"});
  await h.context("main"); assert.equal((await h.read()).review?.verdict, "pending");
  await h.launch(permit.id); await h.context("main");
  assert.equal((await h.read()).review?.verdict, "go");
});

test("background review rejects failed, incomplete, compacted, reused and malformed child transcripts", async t => {
  const h = await harness(t); await h.ready(); await h.authorize(); const permit = await h.permit();
  await h.launch(permit.id);
  h.finished(); const valid = structuredClone(h.transcripts.get("review")!);
  const assistant = valid[1] as Record<string, unknown>;
  const cases: unknown[][] = [
    valid.slice(0, -1),
    [...valid.slice(0, -1), {type:"idle",outcome:"failed"}],
    [valid[0], {...assistant, time:{created:1}}, valid[2]],
    [valid[0], {...assistant, error:{message:"failed"}}, valid[2]],
    [valid[0], {...assistant, agent:"vibe-main"}, valid[2]],
    [valid[0], {...assistant, finish:"length"}, valid[2]],
    [valid[0], {...assistant, content:[{type:"text",text:"not JSON"}]}, valid[2]],
    [valid[0], {...assistant, content:[{type:"text",text:JSON.stringify({verdict:"no-go",findings:[],requiresUserDecision:false})}]}, valid[2]],
    [valid[0], {...assistant, content:[{type:"text",text:JSON.stringify({verdict:"go",findings:[]})}]}, valid[2]],
    [{type:"compaction",status:"completed"}, ...valid],
    [...valid, {type:"user",text:"replace verdict"}, valid[1], valid[2]],
    [valid[0], {...assistant, content:[{type:"reasoning",text:'{"verdict":"go"}'}]}, valid[2]],
  ];
  for (const messages of cases) {
    h.transcripts.set("review", messages); await h.context("main");
    assert.equal((await h.read()).review?.verdict, "pending");
  }
  h.transcripts.set("review", valid); h.sessions.get("review")!.outcome = "interrupted";
  await h.context("main"); assert.equal((await h.read()).review?.verdict, "pending");
  h.sessions.get("review")!.outcome = "succeeded";
  await h.context("main"); assert.equal((await h.read()).review?.verdict, "go");
});

test("background binding survives plugin reload, while reset and stale evidence cannot replay", async t => {
  const h = await harness(t); await h.ready(); await h.authorize(); const first = await h.permit();
  await h.launch(first.id);
  await setup(h.ctx); // Same durable storage, no in-memory child index.
  h.finished(); await writeFile(resolve(h.root,"src.txt"),"changed");
  await h.context("main"); assert.equal((await h.read()).review?.verdict, "pending");
  await h.step("invalidate_verification"); await h.step("begin_verification",{artifacts:["src.txt"]});
  await h.step("verification_passed",{summary:"Rechecked",checks:["test passed"]});
  await h.authorize(); const second = await h.permit(); await h.launch(second.id);
  assert.match(await h.ctl("reset_review"), /invalidated/);
  await h.context("main"); assert.equal((await h.read()).review?.verdict, "pending");
  await h.authorize(); const third = await h.permit();
  await h.launch(first.id); await h.context("main"); assert.equal((await h.read()).review?.verdict,"pending");
  await h.launch(third.id); await setup(h.ctx); await h.context("main");
  assert.equal((await h.read()).review?.verdict, "go");
});

test("background review retains bounded repairs and frozen strict policy", async t => {
  const h = await harness(t); await h.ready(); h.records.set(modeStorageKey("main"),"balanced");
  const finding = {severity:"major",requirement:"A",location:"src.txt",problem:"Wrong",requiredChange:"Fix"};
  for (let round = 0; round < 3; round++) {
    const child = `review-${round}`;
    h.sessions.set(child, {directory:h.root,parentID:"main",agent:"vibe-reviewer"});
    await h.authorize(); const call = await h.permit(); await h.launch(call.id,child);
    h.finished(child,{verdict:"conditional",findings:[finding]}); await h.context("main");
    const task = await h.read(); assert.equal(task.policy,"strict");
    if (round === 2) { assert.equal(task.status,"blocked"); break; }
    assert.equal(task.phase,"implement"); assert.equal(task.review?.repairRounds,round+1);
    await h.step("begin_verification",{artifacts:["src.txt"]});
    await h.step("verification_passed",{summary:"Rechecked",checks:["test passed"]});
  }
});

test("background review invalidates on pause and ownership transfer; child identity is rechecked", async t => {
  const h = await harness(t); await h.ready(); await h.authorize(); const call = await h.permit();
  await h.launch(call.id); h.finished();
  const context = h.ctx.session.context;
  h.ctx.session.context = async input => {
    const messages = await context(input);
    h.sessions.get("review")!.agent = "other";
    return messages;
  };
  await h.context("main"); assert.equal((await h.read()).review?.verdict,"pending");
  h.ctx.session.context = context; h.sessions.get("review")!.agent = "vibe-reviewer";
  await h.step("block",{reason:"Interrupted review"}); await h.ctl("pause");
  await h.context("main"); assert.equal((await h.read()).review?.verdict,"pending");
  assert.match(await h.ctl("resume_blocked",undefined,"other"),/resumed/);
  await h.context("other"); await h.context("main");
  assert.equal((await h.read()).review?.verdict,"pending");
  assert.equal((await h.permit("main")).effect,"deny");
});

test("a background reviewer requiring a user decision blocks immediately", async t => {
  const h = await harness(t); await h.ready(); await h.authorize(); const call = await h.permit();
  await h.launch(call.id);
  h.finished("review", {verdict:"no-go",requiresUserDecision:true,findings:[{
    severity:"major",requirement:"A",location:"src.txt",problem:"Decision required",requiredChange:"User must choose",
  }]});
  await h.context("main");
  const task = await h.read(); assert.equal(task.status,"blocked");
  assert.equal(task.review?.repairRounds,0); assert.match(await h.ctl("close"),/Rejected/);
});
