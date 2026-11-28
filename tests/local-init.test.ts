import assert from 'node:assert/strict';
import test from 'node:test';
import {mkdtemp,mkdir,readFile,readdir,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {execFileSync} from 'node:child_process';
import {initLocal} from '../runtime/opencode/plugins/vibe-v2/team/init-local.ts';
const packPath=resolve(import.meta.dirname,'../shared/team-contracts/templates/engineering-dev.json');
const serverExporter=resolve(import.meta.dirname,'../../team-workspace-workbench/scripts/export-template.ts');
test('canonical template is deterministic and local init matches exactly; existing logs and nested roots stay intact',async t=>{
 const dir=await mkdtemp(join(tmpdir(),'init-refine-'));const env=process.env.OPENCODE_CONFIG_DIR;process.env.OPENCODE_CONFIG_DIR=join(dir,'config');t.after(async()=>{if(env===undefined)delete process.env.OPENCODE_CONFIG_DIR;else process.env.OPENCODE_CONFIG_DIR=env;await rm(dir,{recursive:true,force:true});});
 const root=join(dir,'root');await mkdir(root);const pack=await readFile(packPath,'utf8');assert.equal(execFileSync(process.execPath,['--experimental-strip-types',serverExporter],{encoding:'utf8',stdio:['ignore','pipe','ignore']}),pack);
 await assert.rejects(initLocal(root,'unknown'));const r=await initLocal(root,'engineering-dev');assert.equal(r.files,6);assert.equal(r.version,3);
 for(const f of JSON.parse(pack).files)assert.deepEqual(await readFile(join(root,f.path)),Buffer.from(f.content));
 await writeFile(join(root,'AGENTS.md'),'custom');await writeFile(join(root,'.vibe/progress.md'),'existing knowledge');await assert.rejects(initLocal(root,'engineering-dev'));assert.equal(await readFile(join(root,'AGENTS.md'),'utf8'),'custom');assert.equal(await readFile(join(root,'.vibe/progress.md'),'utf8'),'existing knowledge');
 const sub=join(root,'sub');await mkdir(sub);await assert.rejects(initLocal(sub,'engineering-dev'));assert.deepEqual(await readdir(sub),[]);
});

test('installed offline initializer has the same six files; verify installer actual artifact',async t=>{
 const dir=await mkdtemp(join(tmpdir(),'installed-refine-'));t.after(()=>rm(dir,{recursive:true,force:true}));const cfg=join(dir,'cfg'),root=join(dir,'project');await mkdir(root);
 const src=resolve(import.meta.dirname,'..'), installer=join(src,'scripts/vibe_v2_installer.py');
 execFileSync('python3',[installer,'install','--root',src,'--opencode-home',cfg],{stdio:'pipe'});
 const installed=join(cfg,'runtime/opencode/plugins/vibe-v2/team/init-local.ts');
 const result=execFileSync(process.execPath,['--experimental-strip-types',installed,root,'engineering-dev'],{encoding:'utf8',env:{...process.env,OPENCODE_CONFIG_DIR:cfg,WORKBENCH_URL:'http://127.0.0.1:1'},stdio:['ignore','pipe','ignore']});assert.equal(JSON.parse(result).files,6);assert.equal(JSON.parse(result).version,3);
 for(const f of JSON.parse(await readFile(packPath,'utf8')).files)assert.deepEqual(await readFile(join(root,f.path)),Buffer.from(f.content));
 execFileSync('python3',[installer,'verify','--root',src,'--opencode-home',cfg],{stdio:'pipe'});
});
