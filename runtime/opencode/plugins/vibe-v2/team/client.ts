export class TeamError extends Error {
  readonly code:string;readonly status:number;readonly details?:unknown;
  constructor(code:string,status=0,details?:unknown){super(code);this.code=code;this.status=status;this.details=details;}
}
export function object(value:unknown):Record<string,any> {
  if(!value||typeof value!=="object"||Array.isArray(value))throw new TeamError("invalid_response");return value as Record<string,any>;
}
export class TeamClient {
  readonly serverUrl:string;readonly token:string;
  constructor(serverUrl:string,token:string){this.serverUrl=serverUrl;this.token=token;}
  async request(path:string,method="GET",body?:unknown,headers:Record<string,string>={},deadline=Date.now()+1500,signal?:AbortSignal):Promise<Record<string,any>> {
    if(deadline<=Date.now()||signal?.aborted)throw new TeamError("budget_exhausted");
    const encoded=body===undefined?undefined:JSON.stringify(body);
    if(encoded!==undefined&&Buffer.byteLength(encoded)>2*1024*1024)throw new TeamError("request_too_large");
    const controller=new AbortController(),abort=()=>controller.abort();signal?.addEventListener("abort",abort,{once:true});
    const timer=setTimeout(abort,Math.max(1,deadline-Date.now()));
    try {
      const response=await fetch(`${this.serverUrl}/api${path}`,{method,redirect:"error",signal:controller.signal,
        headers:{authorization:`Bearer ${this.token}`,...(body===undefined?{}:{"content-type":"application/json"}),...headers},
        ...(encoded===undefined?{}:{body:encoded})});
      let bytes=0;const chunks:Uint8Array[]=[];
      if(response.body){for await(const chunk of response.body){bytes+=chunk.byteLength;if(bytes>9*1024*1024){controller.abort();throw new TeamError("response_too_large");}chunks.push(chunk);}}
      if(response.status===401||response.status===403)throw new TeamError("authentication_required",response.status);
      let data:Record<string,any>;try{data=object(JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(Buffer.concat(chunks))));}
      catch{if(!response.ok)throw new TeamError(`http_${response.status}`,response.status);throw new TeamError("invalid_response");}
      if(!response.ok){const status=response.status;throw new TeamError(status===401||status===403?"authentication_required":status===409?"conflict":`http_${status}`,status,data.error?.details);}
      return data;
    } catch(error){if(error instanceof TeamError)throw error;throw new TeamError(controller.signal.aborted?"budget_exhausted":"network_unavailable");}
    finally {clearTimeout(timer);signal?.removeEventListener("abort",abort);}
  }
}
