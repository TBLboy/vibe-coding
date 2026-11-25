import { lstat, mkdir, readdir, readFile, writeFile, rename, unlink, realpath, open } from "node:fs/promises";
import { resolve, sep, dirname } from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { validateServerPath } from "../../../../../shared/team-contracts/layout.ts";
import { hashContent } from "../../../../../shared/team-contracts/manifest.ts";

export const missing=(error:unknown):boolean=>(error as NodeJS.ErrnoException)?.code==="ENOENT";
export const artifact=(path:string):boolean=>/(?:\.conflict-|\.tmp-|\.copy(?:\.|$)|[ -]copy(?:[ .(/-]|$)|\(copy(?: \d+)?\)|副本)/iu.test(path);
function utf8Prefix(name:string,maxBytes:number):string {
  let prefix="",bytes=0;
  for(const point of name){const size=Buffer.byteLength(point);if(bytes+size>maxBytes)break;prefix+=point;bytes+=size;}
  return prefix;
}
export class SafeFiles {
  readonly root:string;
  constructor(root:string){this.root=root;}
  async path(relative:string,create=false):Promise<string> {
    if(!validateServerPath(relative).ok)throw new Error("unsafe path");
    const root=await realpath(this.root), target=resolve(root,relative);
    if(!target.startsWith(root+sep))throw new Error("unsafe path");
    let parent=root;const parts=relative.split("/");
    for(let i=0;i<parts.length;i++) {
      const name=parts[i], candidate=resolve(parent,name), last=i===parts.length-1;
      const names=await readdir(parent);
      if(!names.includes(name) && names.some(n=>n.toLowerCase()===name.toLowerCase()))throw new Error("case collision");
      try {const s=await lstat(candidate);if(s.isSymbolicLink() || (!last&&!s.isDirectory()) || (last&&!s.isFile()))throw new Error("symlink or filesystem collision");}
      catch(error){if(!missing(error))throw error;if(!last){if(!create)return target;await mkdir(candidate,{mode:0o700});}}
      parent=candidate;
    }
    return target;
  }
  async read(relative:string):Promise<Buffer|null> {
    try {const path=await this.path(relative);if((await lstat(path)).size>16*1024*1024)throw new Error("local file too large");return await readFile(path);}catch(error){if(missing(error))return null;throw error;}
  }
  async directory(relative:string):Promise<void> {
    // The guarded probe creates/validates only its parent directories, no file.
    await this.path(`${relative}/.tmp-${randomUUID()}`,true);
  }
  async write(relative:string,bytes:string|Uint8Array,expected?:string|null):Promise<void> {
    const target=await this.path(relative,true), tmp=resolve(dirname(target),`.tmp-${randomUUID()}`);
    try {await writeFile(tmp,bytes,{flag:"wx",mode:0o600});await this.path(relative);
      if(expected!==undefined){const current=await this.read(relative);if((current===null?null:hashContent(current))!==expected)throw new Error("local_changed");}
      await rename(tmp,target);}
    finally {await unlink(tmp).catch(error=>{if(!missing(error))throw error;});}
  }
  async remove(relative:string,expected?:string):Promise<void> {
    try{const target=await this.path(relative);if(expected!==undefined){const current=await this.read(relative);if(current===null||hashContent(current)!==expected)throw new Error("local_changed");}await unlink(target);}
    catch(error){if(!missing(error))throw error;}
  }
  async preserve(relative:string,bytes:Uint8Array):Promise<string> {
    const stamp=new Date().toISOString().replace(/[-:]/gu,"").replace(/\.\d{3}Z$/u,"Z");
    const slash=relative.lastIndexOf("/"),parent=relative.slice(0,slash+1),name=relative.slice(slash+1);
    for(let i=0;i<100;i++) {
      const suffix=`.conflict-${stamp}-${randomBytes(3).toString("hex")}${i?`-${i}`:""}`;
      const copy=`${parent}${utf8Prefix(name,255-Buffer.byteLength(suffix))}${suffix}`;
      const target=await this.path(copy,true);
      try {await writeFile(target,bytes,{flag:"wx",mode:0o600});return copy;}catch(error){if((error as NodeJS.ErrnoException).code!=="EEXIST")throw error;}
    }
    throw new Error("conflict copy collision");
  }
  async scan(relative:string,check:()=>void):Promise<string[]> {
    const output:string[]=[];
    const walk=async(dir:string)=>{
      check();let names:string[];try {await this.path(`${dir}/__probe__`);names=await readdir(resolve(this.root,dir));}catch(error){if(missing(error))return;throw error;}
      for(const name of names.sort()) {
        check();const path=`${dir}/${name}`,s=await lstat(resolve(this.root,path));
        if(s.isSymbolicLink())throw new Error("symlink collision");
        if(s.isDirectory())await walk(path);else if(s.isFile())output.push(path);else throw new Error("filesystem collision");
      }
    };
    await walk(relative);return output;
  }
}
const active=new Set<string>();
export async function withProjectLock<T>(root:string,work:()=>Promise<T>):Promise<T> {
  root=await realpath(root);if(active.has(root))throw new Error("sync busy");active.add(root);
  const files=new SafeFiles(root),relative=".vibe/.sync/lock.json",guard=".vibe/.sync/lock-claim.json",nonce=randomUUID();let acquired=false,guarded=false;
  try {
    const path=await files.path(relative,true);
    try {const handle=await open(await files.path(guard,true),"wx",0o600);guarded=true;await handle.close();}
    catch(error){if((error as NodeJS.ErrnoException).code==="EEXIST")throw new Error("sync busy: acquisition guard");throw error;}
    try {
      for(let attempt=0;attempt<2;attempt++) {
        try {const handle=await open(path,"wx",0o600);acquired=true;try{await handle.writeFile(JSON.stringify({pid:process.pid,at:Date.now(),nonce}));}finally{await handle.close();}break;}
        catch(error) {
          if((error as NodeJS.ErrnoException).code!=="EEXIST")throw error;
          let lock:any;try{lock=JSON.parse((await files.read(relative))!.toString());}catch{throw new Error("sync busy: invalid lock");}
          if(!Number.isSafeInteger(lock.pid)||lock.pid<1||typeof lock.at!=="number"||Date.now()-lock.at<600000)throw new Error("sync busy");
          try{process.kill(lock.pid,0);throw new Error("sync busy");}catch(e){if((e as NodeJS.ErrnoException).code!=="ESRCH")throw new Error("sync busy");}
          await unlink(path);
        }
      }
    } finally {if(guarded){await files.remove(guard);guarded=false;}}
    if(!acquired)throw new Error("sync busy");return await work();
  } finally {
    try {if(acquired){const current=await files.read(relative);if(current&&JSON.parse(current.toString()).nonce===nonce)await files.remove(relative);}}
    finally {active.delete(root);}
  }
}
