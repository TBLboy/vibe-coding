import { realpath } from "node:fs/promises";
import type { HostContext } from "../host-contract.ts";
import { TeamMirror } from "./mirror.ts";
import { workspaceTools } from "./tools.ts";
import { teamContext } from "./context.ts";
import { shouldEnableTeamModules } from "./gate.ts";
import { resolveSyncInterval, startPeriodicSync } from "./periodic-sync.ts";

export async function setupTeam(ctx:HostContext,root:string,memoryRootFor:(sessionID:string)=>Promise<string|null>):Promise<()=>void> {
  root=await realpath(root);const mirror=new TeamMirror(root);
  const allowed=async(sessionID:string)=>{
    try {
      const info=await ctx.session.get({sessionID}) as {parentID?:string;agent?:string};
      return !info.parentID&&info.agent!=="vibe-reviewer"&&await memoryRootFor(sessionID)===root&&await shouldEnableTeamModules(root);
    } catch{return false;}
  };
  await ctx.tool.transform(editor=>{for(const tool of workspaceTools(root,mirror,allowed))editor.add(tool);});
  await ctx.session.hook("context",async event=>{
    if(!await allowed(event.sessionID))return;
    const deadline=Date.now()+1500;
    await mirror.sync();
    try{event.system.push({type:"text",text:await teamContext(root,mirror,deadline)});}
    catch{event.system.push({type:"text",text:"Team mirror unavailable: check manifest and local files; no automatic reset or deletion performed."});}
  });
  // Between turns nothing would reach the server, so a bound project syncs on a timer.
  // Failures are recorded on the mirror and retried by its own backoff, not logged.
  const intervalMs=resolveSyncInterval(process.env.VIBE_TEAM_SYNC_INTERVAL_MS);
  return startPeriodicSync({intervalMs,sync:()=>mirror.sync()});
}
