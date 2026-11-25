/** Real plugin client in a separate process; fixture credentials travel only over IPC. */
import { request } from "node:https";
import { TeamClient } from "../../runtime/opencode/plugins/vibe-v2/team/client.ts";
import { connectDirectory } from "../../runtime/opencode/plugins/vibe-v2/team/binding.ts";
import { TeamMirror } from "../../runtime/opencode/plugins/vibe-v2/team/mirror.ts";

let mirror:TeamMirror|undefined;
process.on("message",async(input:any)=>{
  try {
    let result:unknown;
    if(input.action==="probe") {
      let clientError="unexpected_success",tlsError="unexpected_success";
      try {await new TeamClient(input.url,"").request("/auth/login","POST",{email:input.email,password:input.password});}
      catch(error){clientError=(error as {code?:string}).code??"unknown";}
      // Independent TLS oracle: never sets a custom agent or disables verification.
      tlsError=await new Promise<string>(resolve=>{
        const req=request(`${input.url}/api/healthz`,res=>{res.resume();resolve("unexpected_success");});
        req.setTimeout(5000,()=>req.destroy(new Error("oracle_timeout")));
        req.on("error",error=>resolve((error as NodeJS.ErrnoException).code??"oracle_error"));req.end();
      });
      result={clientError,tlsError};
    } else if(input.action==="bind") {
      result=await connectDirectory(input.root,{serverUrl:input.url,sessionToken:input.sessionToken,key:input.key});
    } else if(input.action==="metadata") {
      result=await new TeamClient(input.url,input.token).request(`/workspaces/${input.workspaceId}`);
    } else if(input.action==="connect") {
      const login=await new TeamClient(input.url,"").request("/auth/login","POST",{email:input.email,password:input.password});
      const connected=await connectDirectory(input.root,{serverUrl:input.url,sessionToken:login.sessionToken,key:input.key});
      mirror=new TeamMirror(input.root);
      result={...connected,sync:await mirror.sync(true)};
    } else if(input.action==="append") {
      if(!mirror)throw new Error("not_connected");
      result=await mirror.recordProgress("progress",input.text,"append");
    } else if(input.action==="sync") {
      if(!mirror)throw new Error("not_connected");
      result=await mirror.sync(true);
    } else if(input.action==="stop") {
      process.disconnect();return;
    } else throw new Error("unknown_action");
    process.send?.({id:input.id,ok:true,result,pid:process.pid});
  } catch(error) {
    const e=error as {code?:string;status?:number};
    process.send?.({id:input.id,ok:false,error:e.code??"worker_failed",status:e.status??0,pid:process.pid});
  }
});
process.send?.({ready:true,pid:process.pid});
