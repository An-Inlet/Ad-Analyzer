const fixture=__CASE__,ids=fixture.ids,expected=fixture.expected;
const $=id=>document.getElementById('planning-'+id),assert=(v,m)=>{if(!v)throw Error(m);};
const realFetch=window.fetch.bind(window),base=`/api/customer/v1/workspaces/${ids.workspace_id}/planning/plans/${ids.plan_id}`;
let originalEvents=null;
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
 if(originalEvents){$('events-refresh').click();await until(()=>settled()&&!$('events').hidden,'explicit customer history read');}
};
const readSales=async(amount,end,days)=>{
 const before=progressCalls;$('progress-read').click();
 await until(()=>settled()&&!$('progress').hidden,'explicit sales progress');
 assert(progressCalls===before+1,'exactly one explicit progress request');
 const visible=$('progress').textContent;
 if(originalEvents){
  const current=await json(await realFetch(base+'/events'));
  assert(JSON.stringify(current.items)===JSON.stringify(originalEvents),'exact immutable customer event history');
  assert($('events').textContent.includes('Accepted For Manual Application')&&$('events').textContent.includes('Not Independently Verified'),'visible independent unverified history');
 }
 assert(visible.includes(`Observed Shopify Merchandise Net Sales: USD ${amount}.000000`),'exact visible observed amount');
 assert(visible.includes(`2026-11-01 to ${end} (exclusive) · ${days} days`),'visible source-local closed prefix');
 assert(visible.includes('America/New_York')&&visible.includes('Manual application is not assessed; attribution is unavailable'),'no causal/manual claim');
};
try{
 await login();await import('/app/assets/planning.mjs');await openPlan();
 assert(progressCalls===0&&$('progress').hidden,'no automatic progress reads');
 const original=await json(await realFetch(base+'/export?version=1'));
 assert(original.document_digest===ids.document_digest&&JSON.stringify(original.document)===JSON.stringify(expected.document),'exact actual prepared artifact');
 if(fixture.generation_stage==='october'){
  const generated=Date.parse(original.document.generated_at),nextMinute=(Math.floor(generated/60000)+1)*60000;
  // Wait naturally for a representable, nonfuture UI minute after actual generation.
  while(Date.now()<nextMinute)await new Promise(r=>setTimeout(r,Math.min(1000,nextMinute-Date.now())));
  const beforeRecord=await json(await realFetch(base));
  assert(beforeRecord.freshness==='current'&&beforeRecord.document_digest===ids.document_digest,'same V1 still current after natural minute wait');
  const current=await json(await realFetch(base));
  assert(current.freshness==='current'&&current.document_digest===ids.document_digest,'original server document remains current before UI records');
  const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change'));};
  for(const type of ['accepted_for_manual_application','customer_reports_applied']){
   change('action',$('action').options[1].value);change('record-type',type);
   $('statement').value=type==='customer_reports_applied'?'I report completing this review outside Inlet; this is not provider verification.':'I reviewed this exact action for manual application.';
   if(type==='customer_reports_applied')$('applied').value=new Date(nextMinute).toISOString().slice(0,16);
   $('confirm-review').checked=true;$('confirm-review').dispatchEvent(new Event('change'));
   assert(!$('record').disabled,'actual UI customer record eligible');$('record').click();
   await until(()=>settled()&&$('message').textContent.includes('customer record was saved'),'actual UI record saved');
  }
  originalEvents=(await json(await realFetch(base+'/events'))).items;
  assert(originalEvents.length===2,'two genuine UI events');
  const report=originalEvents.find(row=>row.event.assertion==='customer_reports_applied').event;
  assert(report.verification==='customer_report_only'&&Date.parse(report.reported_applied_at)>=generated&&Date.parse(report.reported_applied_at)<=Date.now(),'nonfuture post-generation unverified report');
  if(fixture.branch==='goal_changed'){
   const goalPath=`/api/customer/v1/workspaces/${ids.workspace_id}/goals/${ids.goal_id}`;
   const old=await json(await realFetch(goalPath));
   const csrf=document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith('__Host-inlet_csrf=')).split('=')[1];
   const mutate=async(path,method,body)=>json(await realFetch(path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)}));
   const edited=await mutate(goalPath,'PUT',{expected_revision:old.revision,definition:{...old.definition,target_micros:13000000000}});
   const preview=await mutate(goalPath+'/preview','POST',{expected_revision:edited.revision});
   const confirmed=await mutate(goalPath+'/confirm','POST',{expected_revision:edited.revision,preview_id:preview.preview_id,idempotency_key:'q16-browser-goal-edit'});
   assert(confirmed.revision>ids.goal_revision&&confirmed.confirmation_recorded&&confirmed.definition.target_micros===13000000000,'actual revised goal confirmed');
  }
  await operation('initial_day');
  // Changed-goal projection uses real authentication time, not the dated sales clock.
  if(fixture.branch!=='goal_changed')assert((await realFetch(base+'/progress?version=1')).status===401,'matched dated sales path rejects previous session');
  await login();$('refresh').click();await openPlan();
 }
 if(fixture.branch==='goal_changed'){
  const before=progressCalls;$('progress-read').click();await until(()=>settled()&&!$('progress').hidden,'changed-goal progress');
  assert(progressCalls===before+1&&$('progress').textContent.includes('Goal Changed')&&!$('progress').textContent.includes('Observed Shopify Merchandise Net Sales:'),'no replacement sales amount');
  const artifact=await json(await realFetch(base+'/export?version=1'));
  assert(artifact.document_digest===original.document_digest&&JSON.stringify(artifact.document)===JSON.stringify(original.document),'original artifact preserved after goal edit');
  assert(JSON.stringify((await json(await realFetch(base+'/events'))).items)===JSON.stringify(originalEvents),'original events preserved after goal edit');
  await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',original_events:originalEvents})});
 }else{
 await readSales('0','2026-11-03',2);
 if(fixture.branch==='progress'){
  await operation('later_day');assert((await realFetch(base+'/progress?version=1')).status===401,'matched dated sales path rejects previous-day session');
  await login();$('refresh').click();await openPlan();assert($('progress').hidden,'new session clears old progress');
  await readSales('25','2026-11-04',3);
  const later=await json(await realFetch(base+'/export?version=1'));
  assert(later.document_digest===original.document_digest&&JSON.stringify(later.document)===JSON.stringify(original.document),'later ledger leaves V1 immutable');
  await operation('refund_correction');await login();$('refresh').click();await openPlan();
  await readSales('20','2026-11-04',3);
  const corrected=await json(await realFetch(base+'/export?version=1'));
  assert(corrected.document_digest===original.document_digest&&JSON.stringify(corrected.document)===JSON.stringify(original.document),'real refund preserves original artifact');
  assert(JSON.stringify(corrected.document.inputs.goal)===JSON.stringify(original.document.inputs.goal),'original confirmed goal unchanged');
  await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',document_bytes:JSON.stringify(corrected.document),original_events:originalEvents})});
 }else if(fixture.branch==='session_replacement'){
  const before=await json(await realFetch('/api/customer/v1/session')),cookies=document.cookie;
  await operation('hold');observeNextProgress=true;$('progress-read').click();
  await until(async()=>Boolean((await json(await realFetch('/__fixture__/held'))).held),'valid old-session progress held');
  await login();const after=await json(await realFetch('/api/customer/v1/session'));
  assert(after.user_id===before.user_id&&after.expires_at===before.expires_at&&document.cookie!==cookies,'same-owner same-time session rotation');
  $('refresh').click();await openPlan();assert($('progress').hidden&&!$('progress').textContent,'replacement clears old progress');
  await operation('release');assert(heldRead!==null,'held replacement request observed');await heldRead;await new Promise(r=>setTimeout(r,0));
  assert($('progress').hidden&&!$('progress').textContent&&!$('document').hidden,'late old-session bytes rejected while original plan remains');
  assert(JSON.stringify((await json(await realFetch(base+'/events'))).items)===JSON.stringify(originalEvents),'new session retains authentic history');
  const artifact=await json(await realFetch(base+'/export?version=1'));
  assert(artifact.document_digest===original.document_digest&&JSON.stringify(artifact.document)===JSON.stringify(original.document),'same plan remains accessible');
  await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',original_events:originalEvents})});
 }else{
  await operation('hold');observeNextProgress=true;$('progress-read').click();
  await until(async()=>Boolean((await json(await realFetch('/__fixture__/held'))).held),'actual computed progress held');
  await operation('erase');$('refresh').click();
  await until(()=>settled()&&$('document').hidden&&$('progress').hidden,'explicit refresh clears erased plan');
  await operation('release');assert(heldRead!==null,'held browser request observed');
  await heldRead;
  // The controller's await-fetch continuation and rejection handlers run before this task.
  await new Promise(r=>setTimeout(r,0));
  assert($('document').hidden&&$('progress').hidden&&!$('progress').textContent&&!$('events').textContent,'late real response cannot repopulate after epoch change');
  $('workspace').value=String(ids.workspace_id);$('workspace').dispatchEvent(new Event('change'));
  await until(()=>settled(),'refresh erased workspace');assert(!$('plans').querySelector('button'),'erased plan absent from actual list');
  for(const path of [base,base+'/progress?version=1',base+'/export?version=1',base+'/versions/1',base+'/versions',base+'/events'])assert((await realFetch(path)).status===404,'old erased ID unavailable');
  assert($('document').hidden&&$('progress').hidden,'old ID reads do not restore DOM');
  await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',original_events:originalEvents})});
 }
 }
}catch(error){await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack,original_events:originalEvents})});}
