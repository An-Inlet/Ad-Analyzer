const fixture=__CASE__,ids=fixture.ids,expected=fixture.expected;
const $=id=>document.getElementById('planning-'+id),assert=(v,m)=>{if(!v)throw Error(m);};
const realFetch=window.fetch.bind(window),base=`/api/customer/v1/workspaces/${ids.workspace_id}/planning/plans/${ids.plan_id}`;
let progressCalls=0,logins=0,observeNextProgress=false,heldRead=null;
window.fetch=(input,options)=>{
 const progress=String(input).includes(base+'/progress');if(progress)progressCalls++;
 const response=realFetch(input,options);
 if(progress&&observeNextProgress){
  observeNextProgress=false;
  heldRead=response.then(async actual=>{
   // Observe the complete real bytes on a clone; return the identical original Response.
   const bytes=await actual.clone().arrayBuffer();
   assert(actual.status===200&&bytes.byteLength>0,'held real successful body consumed');
   return actual;
  });
  return heldRead;
 }
 return response;
};
const until=async(fn,message)=>{const end=Date.now()+15000;while(!await fn()){if(Date.now()>end)throw Error(message+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const settled=()=>!$('list-refresh').disabled;
const json=async response=>{assert(response.ok,'real API success '+response.status);return response.json();};
const operation=async name=>json(await realFetch('/__fixture__/'+name,{method:'POST'}));
const login=async()=>{assert((await realFetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'q16-browser-'+(++logins)})})).ok,'actual HTTPS session issuance');};
const openPlan=async()=>{
 await until(()=>settled()&&$('workspace').options.length>1,'owned session choices');
 $('workspace').value=String(ids.workspace_id);$('workspace').dispatchEvent(new Event('change'));
 await until(()=>settled()&&$('plans').querySelector('button'),'owned saved plan');
 $('plans').querySelector('button').click();await until(()=>settled()&&!$('document').hidden,'immutable plan displayed');
 assert($('document').textContent.includes('Plan Version 1'),'same V1');
 assert($('document').textContent.includes('current_reporting_unavailable'),'missing reporting remains explicit');
 assert($('document').textContent.includes('12000'),'original $12000 goal visible');
};
const readSales=async(amount,end,days)=>{
 const before=progressCalls;$('progress-read').click();
 await until(()=>settled()&&!$('progress').hidden,'explicit sales progress');
 assert(progressCalls===before+1,'exactly one explicit progress request');
 const visible=$('progress').textContent;
 assert(visible.includes(`Observed Shopify Merchandise Net Sales: USD ${amount}.000000`),'exact visible observed amount');
 assert(visible.includes(`2026-11-01 to ${end} (exclusive) · ${days} days`),'visible source-local closed prefix');
 assert(visible.includes('America/New_York')&&visible.includes('Manual application is not assessed; attribution is unavailable'),'no causal/manual claim');
};
try{
 await login();await import('/app/assets/planning.mjs');await openPlan();
 assert(progressCalls===0&&$('progress').hidden,'no automatic progress reads');
 const original=await json(await realFetch(base+'/export?version=1'));
 assert(original.document_digest===ids.document_digest&&JSON.stringify(original.document)===JSON.stringify(expected.document),'exact actual prepared artifact');
 await readSales('0','2026-11-03',2);
 if(fixture.branch==='progress'){
  await operation('later_day');assert((await realFetch(base+'/progress?version=1')).status===401,'ordinary previous session expired next day');
  await login();$('refresh').click();await openPlan();assert($('progress').hidden,'new session clears old progress');
  await readSales('25','2026-11-04',3);
  const later=await json(await realFetch(base+'/export?version=1'));
  assert(later.document_digest===original.document_digest&&JSON.stringify(later.document)===JSON.stringify(original.document),'later ledger leaves V1 immutable');
  await operation('refund_correction');await login();$('refresh').click();await openPlan();
  await readSales('20','2026-11-04',3);
  const corrected=await json(await realFetch(base+'/export?version=1'));
  assert(corrected.document_digest===original.document_digest&&JSON.stringify(corrected.document)===JSON.stringify(original.document),'real refund preserves original artifact');
  assert(JSON.stringify(corrected.document.inputs.goal)===JSON.stringify(original.document.inputs.goal),'original confirmed goal unchanged');
  await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',document_bytes:JSON.stringify(corrected.document)})});
 }else{
  await operation('hold');observeNextProgress=true;$('progress-read').click();
  await until(async()=>Boolean((await json(await realFetch('/__fixture__/held'))).held),'actual computed progress held');
  await operation('erase');$('refresh').click();
  await until(()=>settled()&&$('document').hidden&&$('progress').hidden,'explicit refresh clears erased plan');
  await operation('release');assert(heldRead!==null,'held browser request observed');
  await heldRead;
  // The controller's await-fetch continuation and rejection handlers run before this task.
  await new Promise(r=>setTimeout(r,0));
  assert($('document').hidden&&$('progress').hidden&&!$('progress').textContent,'late real response cannot repopulate after epoch change');
  $('workspace').value=String(ids.workspace_id);$('workspace').dispatchEvent(new Event('change'));
  await until(()=>settled(),'refresh erased workspace');assert(!$('plans').querySelector('button'),'erased plan absent from actual list');
  for(const path of [base,base+'/progress?version=1',base+'/export?version=1',base+'/versions/1'])assert((await realFetch(path)).status===404,'old erased ID unavailable');
  assert($('document').hidden&&$('progress').hidden,'old ID reads do not restore DOM');
  await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
 }
}catch(error){await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
