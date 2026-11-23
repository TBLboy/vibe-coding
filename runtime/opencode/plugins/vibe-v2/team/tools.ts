import type { ToolDefinition } from "../host-contract.ts";
import { loadBinding, connectDirectory } from "./binding.ts";
import { TeamError } from "./client.ts";
import { TeamMirror } from "./mirror.ts";
import { validateServerPath } from "../../../../core/team/layout.ts";

export function workspaceTools(root:string,mirror:TeamMirror,allowed:(sessionID:string)=>Promise<boolean>):ToolDefinition[] {
  const specs:{name:string;properties:Record<string,unknown>;required?:string[];run:(input:Record<string,unknown>,signal?:AbortSignal)=>Promise<unknown>}[]=[
    {name:"workspace_connect",properties:{force:{type:"boolean"}},run:async(i,s)=>{
      const binding=await loadBinding(root);if(!binding)throw new TeamError("binding_missing");
      const sessionToken=process.env.TEAM_SESSION_TOKEN,key=process.env.TEAM_TASK_KEY;
      if(!sessionToken||!key)throw new TeamError("credentials_environment_required: run the local connector outside the conversation; never paste secrets into tool input");
      return connectDirectory(root,{serverUrl:binding.serverUrl,sessionToken,key,force:i.force===true},s);
    }},
    {name:"workspace_status",properties:{},run:()=>mirror.inspect()},
    {name:"workspace_sync",properties:{},run:(_,s)=>mirror.sync(true,s)},
    {name:"workspace_record_progress",properties:{kind:{type:"string",enum:["progress","session"]},text:{type:"string"},mode:{type:"string",enum:["append","replace"]}},required:["kind","text"],run:(i,s)=>mirror.recordProgress(i.kind,i.text,i.mode??"append",s)},
    {name:"workspace_task_declare",properties:{title:{type:"string"},scope:{type:"array",items:{type:"string"}},note:{type:"string"}},required:["title"],run:(i,s)=>mirror.task("declare",i,s)},
    {name:"workspace_task_claim",properties:{id:{type:"string"}},required:["id"],run:(i,s)=>mirror.task("claim",i,s)},
    {name:"workspace_task_update",properties:{id:{type:"string"},status:{type:"string",enum:["done","abandoned"]},reason:{type:"string"}},required:["id","status"],run:(i,s)=>mirror.task("status",i,s)},
    {name:"workspace_query_spec",properties:{path:{type:"string"}},required:["path"],run:async i=>{
      if(typeof i.path!=="string"||!i.path.startsWith("specs/")||!validateServerPath(i.path).ok)throw new TeamError("invalid_spec_path");
      const data=await mirror.files.read(`.vibe/${i.path}`);return data?{path:i.path,content:data.toString("utf8")}:{status:"not_mirrored"};
    }},
  ];
  return specs.map(spec=>({name:spec.name,description:`Bound team workspace: ${spec.name}. No task queue; local mirrors may be stale.`,
    input:{type:"object",properties:spec.properties,required:spec.required??[],additionalProperties:false},
    execute:async(input,context)=>{
      if(context.agent!=="vibe-main"||!await allowed(context.sessionID))return {content:"Rejected: workspace Session mismatch or reviewer."};
      try{return {content:JSON.stringify(await spec.run(input,context.signal))};}
      catch(error){const value:Record<string,unknown>={error:error instanceof TeamError?error.code:"local_workspace_failed"};
        if(error instanceof TeamError&&error.status===409){const d=error.details as {claimedBy?:unknown;status?:unknown}|undefined;
          if(typeof d?.claimedBy==="string"&&/^[A-Za-z0-9_-]{1,128}$/u.test(d.claimedBy))value.claimedBy=d.claimedBy;}
        return {content:JSON.stringify(value)};}
    }}));
}
