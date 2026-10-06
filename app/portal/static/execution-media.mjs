// Exact owned bytes only; each independent panel cancels and revokes its old preview.
const previews=new Map(), limit=64*1024*1024;
export function clearMedia(kind){
 const previous=previews.get(kind);previews.delete(kind);
 if(previous){previous.abort.abort();for(const url of previous.urls)URL.revokeObjectURL(url);}
 const panel=document.getElementById(`execution-${kind}-media`);
 if(panel){for(const video of panel.querySelectorAll('video')){video.pause();video.removeAttribute('src');video.load();}panel.replaceChildren();}
}
export async function showMedia(kind,workspace,configuration,active){
 clearMedia(kind);
 const panel=document.getElementById(`execution-${kind}-media`), state={abort:new AbortController(),urls:[]};
 previews.set(kind,state);
 const current=()=>previews.get(kind)===state&&!state.abort.signal.aborted&&active();
 const timer=setTimeout(()=>state.abort.abort(),30000), status=document.createElement('p');
 status.setAttribute('role','status');status.textContent='Loading Exact Private Media…';panel.append(status);
 try{
  const bindings=configuration.image?[['Image',configuration.image]]:[['Video',configuration.video],['Cover Image',configuration.cover]];
  for(const [label,binding] of bindings){
   if(!binding||!['image/png','image/jpeg','image/webp','video/mp4'].includes(binding.mime)||binding.byte_size>limit)throw new Error('Reviewed media is unavailable.');
   const response=await fetch(`/api/customer/v1/workspaces/${encodeURIComponent(workspace)}/media/${encodeURIComponent(binding.media_id)}`,{credentials:'same-origin',redirect:'error',cache:'no-store',signal:state.abort.signal});
   if(!current())return false;
   if(!response.ok||!response.body||response.headers.get('content-type')?.split(';')[0]!==binding.mime)throw new Error('Reviewed media is unavailable.');
   const reader=response.body.getReader(),chunks=[];let size=0;
   try{while(true){const {value,done}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit||size>binding.byte_size)throw new Error('Reviewed media exceeds its exact size.');chunks.push(value);}}
   catch(error){await reader.cancel();throw error;}
   if(!current())return false;
   if(size!==binding.byte_size)throw new Error('Reviewed media size changed.');
   const blob=new Blob(chunks,{type:binding.mime});
   const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await blob.arrayBuffer())),b=>b.toString(16).padStart(2,'0')).join('');
   if(!current())return false;
   if(hash!==binding.sha256)throw new Error('Reviewed media changed.');
   const caption=document.createElement('p');caption.textContent=`${label} · ${binding.width} × ${binding.height} · File ${hash.slice(0,12)}`;panel.append(caption);
   const media=document.createElement(binding.mime==='video/mp4'?'video':'img');
   if(media.tagName==='VIDEO'){media.controls=true;media.preload='auto';media.muted=true;}else media.alt=`Exact Reviewed ${label}`;
   media.style.maxWidth='320px';media.style.maxHeight='240px';panel.append(media);
   const url=URL.createObjectURL(blob);state.urls.push(url);
   await new Promise((resolve,reject)=>{
    const event=media.tagName==='VIDEO'?'loadeddata':'load';
    const cleanup=()=>{media.removeEventListener(event,success);media.removeEventListener('error',failure);state.abort.signal.removeEventListener('abort',failure);};
    const success=()=>{cleanup();resolve();};
    const failure=()=>{cleanup();reject(new Error('The exact reviewed media could not be decoded.'));};
    media.addEventListener(event,success,{once:true});media.addEventListener('error',failure,{once:true});state.abort.signal.addEventListener('abort',failure,{once:true});media.src=url;
   });
  }
  if(!current())return false;status.textContent='Exact Private Media Loaded';return true;
 }catch(error){if(current()){clearMedia(kind);status.textContent=error.message;panel.append(status);}return false;}
 finally{clearTimeout(timer);if(previews.get(kind)===state){const activeNow=active();if(!activeNow||state.abort.signal.aborted){const timedOut=activeNow&&state.abort.signal.aborted;clearMedia(kind);if(timedOut){status.textContent='Private media load timed out.';panel.append(status);}}}}
}
