import { loadBinding } from "./binding.ts";
export async function shouldEnableTeamModules(root:string):Promise<boolean> {
  try{return (await loadBinding(root))!==null;}catch{return false;}
}
