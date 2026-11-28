import {createHash} from 'node:crypto';
import {lstat,mkdir,readdir,readFile,realpath,rmdir,unlink,open} from 'node:fs/promises';
import {dirname,join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {loadDeviceBinding,stateDir,withStateLock} from './device-state.ts';
import {validateSyncPath} from '../../../../../shared/team-contracts/layout.ts';
import {validText,MAX_DOCUMENT_BYTES,pathsCollide} from '../../../../../shared/team-contracts/limits.ts';
import {SafeFiles,missing} from './files.ts';
async function exists(p:string):Promise<boolean>{try{await lstat(p);return true;}catch(e){if(missing(e))return false;throw e;}}
export async function initLocal(root:string,type:string):Promise<{root:string;type:string;version:number;files:number}>{
  root=await realpath(root);
  if(type!=='engineering-dev')throw new Error('unsupported workspace type');
  const pack=JSON.parse(await readFile(new URL('../../../../../shared/team-contracts/templates/engineering-dev.json',import.meta.url),'utf8'));
  if(pack.type!==type||!Number.isSafeInteger(pack.version)||!Array.isArray(pack.files)||pack.files.length!==6||createHash('sha256').update(JSON.stringify({type:pack.type,version:pack.version,files:pack.files})).digest('hex')!==pack.sha256)throw new Error('invalid template pack');
  const files=pack.files as {path:string;content:string}[],seen=new Set<string>();
  for(const f of files){if(!validateSyncPath(f.path).ok||typeof f.content!=='string'||!validText(f.content)||Buffer.byteLength(f.content)>MAX_DOCUMENT_BYTES||seen.has(f.path)||[...seen].some(p=>pathsCollide(p,f.path)))throw new Error('invalid template file');seen.add(f.path);}
  const privateDir=stateDir(root);
  try{return await withStateLock(privateDir,async()=>{
    for(let d=root;;d=dirname(d)){
      const entries=await readdir(d);if(entries.some(n=>n.toLowerCase()==='.vibe')||(d===root&&entries.some(n=>n.toLowerCase()==='agents.md'))||await loadDeviceBinding(stateDir(d)))throw new Error('existing project memory or binding; no initialization performed');
      if(dirname(d)===d)break;
    }
    const safe=new SafeFiles(root), created:{path:string;content:string}[]=[], dirs:string[]=[];
    try{
      await mkdir(join(root,'.vibe'),{mode:0o700});dirs.push(join(root,'.vibe'));
      for(const f of files){const parent=dirname(join(root,f.path));if(parent!==root&&parent!==join(root,'.vibe')&&!await exists(parent)){await safe.path(f.path);await mkdir(parent,{mode:0o700});dirs.push(parent);}
        const target=await safe.path(f.path);const handle=await open(target,'wx',0o600);created.push({path:target,content:f.content});try{await handle.writeFile(f.content);}finally{await handle.close();}}
      for(const f of files)if(!(await safe.read(f.path))?.equals(Buffer.from(f.content)))throw new Error('template verification failed');
      return {root,type,version:pack.version,files:files.length};
    }catch(e){let residual=false;for(const f of created.reverse())try{const st=await lstat(f.path);if(st.isFile()&&(await readFile(f.path)).equals(Buffer.from(f.content)))await unlink(f.path);else residual=true;}catch{residual=true;}
      for(const d of dirs.reverse())try{await rmdir(d);}catch{residual=true;}
      if(residual)throw new Error('initialization failed; inspect these attempted paths for residual files: '+created.map(f=>f.path).concat(dirs).join(', '));throw e;}
  });}finally{await rmdir(privateDir).catch(()=>{});}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  initLocal(resolve(process.argv[2]??'.'),process.argv[3]??'').then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error(e instanceof Error?e.message:'initialization failed');process.exitCode=1;});
}
