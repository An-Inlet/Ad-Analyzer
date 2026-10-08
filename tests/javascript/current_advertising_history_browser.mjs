const wid=__WORKSPACE__,realFetch=fetch,assert=(v,m)=>{if(!v)throw Error(m);},$=id=>document.getElementById('history-'+id);
const until=async(fn,label)=>{let deadline=Date.now()+10000;while(!fn()){if(Date.now()>deadline)throw Error(label+': '+$('status').textContent);await new Promise(r=>setTimeout(r,20));}};
const login=async token=>{const r=await realFetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:token})});assert(r.ok,'actual sign in');};
try{
 await login('history-owner:browser');let mutation=0;
 globalThis.fetch=async(...args)=>{if(String(args[0]).includes('/execution/')&&(args[1]?.method||'GET')!=='GET')mutation++;return realFetch(...args);};
 await import('/app/assets/advertising-history.mjs');await until(()=>$('workspace').options.length===2&&!$('read').disabled,'owned workspaces');
 assert(!document.querySelector('input,textarea,form'),'no retired action forms');assert([...document.querySelectorAll('button')].map(n=>n.id).sort().join(',')==='history-read,history-refresh','only read/session buttons');
 $('workspace').value=String(wid);$('workspace').dispatchEvent(new Event('change'));$('read').click();await until(()=>$('status').textContent==='No retained advertising runs.','actual scoped history');assert(mutation===0,'history never writes');
 await login('history-outsider:browser');$('read').click();await until(()=>$('status').textContent.includes('session changed'),'old display session fence');assert(!$('result').textContent,'old history cleared');$('refresh').click();await until(()=>$('workspace').options.length===1&&!$('read').disabled,'foreign customer has no owned workspace');
 const foreign=await realFetch(`/api/customer/v1/workspaces/${wid}/execution/runs`);assert([403,404].includes(foreign.status),'foreign scoped history denied');assert(mutation===0,'no advertising writes');
 await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(e){await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:e.message,stack:e.stack})});}
