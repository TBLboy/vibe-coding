import assert from "node:assert/strict";
import test from "node:test";
import { mkdtemp, mkdir, writeFile, readFile, rm, realpath, symlink, link } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { searchReviewWorkspace } from "../runtime/opencode/plugins/vibe-v2/reviewer-search.ts";

async function fixture(t: {after(fn:()=>Promise<void>):void}) {
  const base=await realpath(await mkdtemp(resolve(tmpdir(),"vibe-review-search-")));
  t.after(()=>rm(base,{recursive:true,force:true}));
  const root=resolve(base,"project"); await mkdir(resolve(root,"src"),{recursive:true});
  await writeFile(resolve(root,"src/consumer.ts"),"function call() {}\ncall();\ncall() // private text not returned\n");
  await writeFile(resolve(root,"src/other.ts"),"not relevant\n");
  return {base,root};
}

test("literal locator finds actual line locations and names without returning file content",async t=>{
  const {root}=await fixture(t);
  const before=await readFile(resolve(root,"src/consumer.ts"));
  const result=await searchReviewWorkspace(root,{kind:"text",query:"call()",scope:"src"});
  assert.deepEqual(result.matches,[1,2,3].map(line=>({path:"src/consumer.ts",line})));
  assert.ok(!JSON.stringify(result).includes("private text"));
  assert.deepEqual((await searchReviewWorkspace(root,{kind:"files",query:"consumer"})).matches,[{path:"src/consumer.ts"}]);
  assert.deepEqual((await searchReviewWorkspace(root,{kind:"text",query:"call.*"})).matches,[]); // not a regex
  assert.deepEqual(await readFile(resolve(root,"src/consumer.ts")),before);
});

test("protected, generated, outside, symlink and hardlink paths cannot become search results",async t=>{
  const {base,root}=await fixture(t); const marker="PROTECTED_MARKER";
  for(const path of [".env",".env.production","src/.npmrc","src/credentials.json","auth.json","src/ID_RSA","server.pem",".git/config","node_modules/pkg/index.ts","secrets/private.txt","src/service-account-a.json"]) {
    const full=resolve(root,path); await mkdir(resolve(full,".."),{recursive:true}); await writeFile(full,marker);
  }
  await writeFile(resolve(base,"outside.txt"),marker); let symlinks=true;
  try { await symlink(resolve(base,"outside.txt"),resolve(root,"src/link.txt"),"file"); await symlink(base,resolve(root,"src/linkdir"),"dir"); }
  catch(e) { if((e as NodeJS.ErrnoException).code!=="EPERM") throw e; symlinks=false; } await link(resolve(base,"outside.txt"),resolve(root,"src/hardlink.txt"));
  await writeFile(resolve(root,"src/binary.txt"),Buffer.from([0,...Buffer.from(marker)]));
  await writeFile(resolve(root,"src/large.txt"),marker+"x".repeat(512*1024));
  const result=await searchReviewWorkspace(root,{kind:"text",query:marker}); assert.deepEqual(result.matches,[]); assert.ok(result.skipped>0);
  for(const scope of (["../outside.txt",resolve(base,"outside.txt"),"src/../.env","src\\link.txt","src/link.txt","src/linkdir",".env",".git","secrets","src/credentials.json","C:/Windows"]).filter(s=>symlinks||!/link(\.txt|dir)$/.test(s))) await assert.rejects(searchReviewWorkspace(root,{kind:"text",query:marker,scope}));
  assert.deepEqual((await searchReviewWorkspace(root,{kind:"files",query:"link"})).matches,[]);
  const artifacts=await searchReviewWorkspace(root,{kind:"artifacts"},undefined,["src/consumer.ts",".env","../outside.txt",".git/config"]);
  assert.deepEqual(artifacts.matches,[{path:"src/consumer.ts"}]); assert.equal(artifacts.skipped,3);
});

test("locator reports bounded partial results, invalid input and cancellation",async t=>{
  const {root}=await fixture(t);
  await writeFile(resolve(root,"src/many.ts"),"line\n".repeat(110));
  const result=await searchReviewWorkspace(root,{kind:"text",query:"line",scope:"src/many.ts"});
  assert.equal(result.matches.length,100); assert.equal(result.truncated,true);
  const inventory=await searchReviewWorkspace(root,{kind:"artifacts"},undefined,Array.from({length:101},(_,i)=>`src/${i}.ts`));
  assert.equal(inventory.matches.length,100); assert.equal(inventory.truncated,true);
  for(const input of [{kind:"shell",query:"git status"},{kind:"text",query:""},{kind:"text",query:"x".repeat(201)},{kind:"text",query:"a\nb"},{kind:"text",query:"call",extra:true}]) await assert.rejects(searchReviewWorkspace(root,input));
  const abort=new AbortController(); abort.abort(); await assert.rejects(searchReviewWorkspace(root,{kind:"text",query:"call"},abort.signal));
});


test("content search authorizes candidates before reading and can narrow artifact inventory",async t=>{
  const {root}=await fixture(t);
  const denied=async (paths:string[])=>{assert.ok(paths.includes("src/consumer.ts")); throw new Error("read denied");};
  // A denied file with NO matching line still requires authorization before scanning it.
  await assert.rejects(searchReviewWorkspace(root,{kind:"text",query:"absent"},undefined,[],denied),/read denied/);
  const paths=["src/consumer.ts","src/other.ts","tests/consumer.test.ts"];
  const inventory=await searchReviewWorkspace(root,{kind:"artifacts",scope:"src",query:"consumer"},undefined,paths);
  assert.deepEqual(inventory.matches,[{path:"src/consumer.ts"}]);
});
