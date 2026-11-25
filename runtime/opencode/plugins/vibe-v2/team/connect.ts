import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { connectDirectory } from "./binding.ts";
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href) {
  const {TEAM_SERVER_URL:serverUrl,TEAM_SESSION_TOKEN:sessionToken,TEAM_TASK_KEY:key}=process.env;
  if(!serverUrl||!sessionToken||!key){process.stderr.write("TEAM_SERVER_URL, TEAM_SESSION_TOKEN and TEAM_TASK_KEY are required\n");process.exitCode=1;}
  else connectDirectory(resolve(process.argv[2]??"."),{serverUrl,sessionToken,key})
    .then(()=>process.stdout.write("Connected. Use /reload to load workspace tools.\n"))
    .catch(()=>{process.stderr.write("Connection failed: verify the server, credentials, membership and existing directory binding.\n");process.exitCode=1;});
}
