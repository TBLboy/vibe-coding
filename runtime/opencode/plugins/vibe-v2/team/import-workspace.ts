import {realpath} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {scanSyncFiles} from './scan.ts';
import {SafeFiles} from './files.ts';
import {TeamClient} from './client.ts';
import {decodeText,MAX_DOCUMENT_BYTES,MAX_IMPORT_BODY,pathsCollide} from '../../../../../shared/team-contracts/limits.ts';
export async function importWorkspace(root:string,name:string,type:string,serverUrl:string,token:string){
  root=await realpath(root);if(type!=='engineering-dev')throw new Error('unsupported workspace type');
  const url=new URL(serverUrl);if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.hash||url.search)throw new Error('invalid server URL');
  if(url.protocol!=='https:'&&!['localhost','127.0.0.1','[::1]'].includes(url.hostname))throw new Error('HTTPS required for remote administrator credentials');
  const scan=await scanSyncFiles(root);if(scan.warnings.length)throw new Error('import refused: '+scan.warnings.join('; '));
  if(!scan.files.includes('AGENTS.md')||!scan.files.includes('.vibe/progress.md'))throw new Error('required engineering log files missing');
  const safe=new SafeFiles(root),files:{path:string;content:string}[]=[];
  for(const path of scan.files){const bytes=await safe.read(path);if(!bytes||bytes.length>MAX_DOCUMENT_BYTES||files.some(f=>pathsCollide(f.path,path)))throw new Error('source changed or invalid');files.push({path,content:decodeText(bytes)});}
  const checked=await scanSyncFiles(root);
  if(checked.warnings.length||JSON.stringify(checked.files)!==JSON.stringify(scan.files))throw new Error('source changed during collection');
  for(const f of files){const b=await safe.read(f.path);if(!b?.equals(Buffer.from(f.content)))throw new Error('source changed during collection: '+f.path);}
  const body={name,type,files};if(Buffer.byteLength(JSON.stringify(body))>MAX_IMPORT_BODY)throw new Error('import request too large');
  return new TeamClient(serverUrl.replace(/\/+$/u,''),token).request('/workspaces/import','POST',body,{},Date.now()+60000);
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  const {WORKBENCH_URL:url,WORKBENCH_ADMIN_TOKEN:token}=process.env;
  if(!url||!token||!process.argv[3]||!process.argv[4]){console.error('WORKBENCH_URL, WORKBENCH_ADMIN_TOKEN and arguments root name type required');process.exitCode=1;}
  else importWorkspace(process.argv[2]??'.',process.argv[3],process.argv[4],url,token).then(r=>console.log(JSON.stringify(r))).catch(e=>{console.error('Import failed or outcome unknown; check workspace list before retrying. '+(e instanceof Error?e.message:''));process.exitCode=1;});
}
