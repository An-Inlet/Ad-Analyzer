import {imageMetadata} from './plan-creative-inputs.mjs';
// Same-origin owned bytes only. No URLs, credentials or successful IDs supplied by the customer.
export async function planningMediaRequest({workspaceId,value,signal,cookies,check}){
 check();if(!Number.isSafeInteger(workspaceId)||workspaceId<=0)throw Error('Workspace image unavailable.');
 const upload=value instanceof File;
 if(upload?(!['image/png','image/jpeg'].includes(value.type)||value.size<=0||value.size>8388608):!imageMetadata(value))throw Error('Choose a supported PNG or JPEG image.');
 const controller=new AbortController(),abort=()=>controller.abort();signal.addEventListener('abort',abort,{once:true});if(signal.aborted)abort();const timer=setTimeout(abort,30000);
 try{
  const headers={Accept:upload?'application/json':value.mime};
  if(upload){const csrf=cookies.split(';').map(v=>v.trim()).find(v=>v.startsWith('__Host-inlet_csrf='))?.slice('__Host-inlet_csrf='.length);if(!/^[A-Za-z0-9_-]{43}$/.test(csrf||''))throw Error('Refresh your session before uploading.');headers['X-CSRF-Token']=csrf;headers['Content-Type']='application/octet-stream';}
  const response=await fetch(`/api/customer/v1/workspaces/${workspaceId}/media${upload?'':'/'+value.media_id}`,{method:upload?'POST':'GET',headers,body:upload?value:undefined,credentials:'same-origin',cache:'no-store',redirect:'error',signal:controller.signal});check();
  if(!response.ok)throw Object.assign(Error('Workspace image unavailable. Review access and the library before retrying.'),{status:response.status});
  if(!upload&&response.headers.get('Content-Type')?.split(';')[0]!==value.mime)throw Error('Image metadata changed. Read the library again.');
  const reader=response.body?.getReader();if(!reader)throw Error('Workspace image response unavailable.');const chunks=[];let size=0;const limit=upload?65536:value.size;
  try{while(true){const part=await reader.read();check();if(controller.signal.aborted)throw Error('Workspace image request expired.');if(part.done)break;size+=part.value.byteLength;if(size>limit)throw Error('Workspace image response exceeds its bound.');chunks.push(part.value);}}finally{await reader.cancel();reader.releaseLock();}
  check();if(controller.signal.aborted)throw Error('Workspace image request expired.');
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
  if(upload){const result=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));if(!imageMetadata(result)||result.size!==value.size||result.mime!==value.type)throw Error('The uploaded image is unsupported. Only matching PNG and JPEG images can be selected.');const uploaded=await value.arrayBuffer();check();const actual=[...new Uint8Array(await crypto.subtle.digest('SHA-256',uploaded))].map(v=>v.toString(16).padStart(2,'0')).join('');check();if(controller.signal.aborted||actual!==result.sha256)throw Error('The upload receipt could not be verified.');return result;}
  if(size!==value.size)throw Error('Image metadata changed. Read the library again.');
  const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');check();if(controller.signal.aborted||digest!==value.sha256)throw Error('Image content could not be verified.');return new Blob([bytes],{type:value.mime});
 }finally{clearTimeout(timer);signal.removeEventListener('abort',abort);controller.abort();}
}
