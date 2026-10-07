const $=id=>document.getElementById(id), assert=(ok,message)=>{if(!ok)throw new Error(message);};
const until=async(test,message)=>{const end=Date.now()+20000;while(!test()){if(Date.now()>end)throw new Error(message+' · '+$('execution-message').textContent);await new Promise(r=>setTimeout(r,20));}};
try{
assert((await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'social-execution-owner:browser'})})).ok,'actual login');
await import('/app/assets/execution.mjs');await until(()=>$('execution-workspace').options.length===2&&!$('execution-refresh').disabled,'workspaces');
assert($('execution-workspace').textContent.includes('<img src=x>')&&!document.querySelector('img'),'workspace rendered literally');
$('execution-workspace').value='__WORKSPACE__';$('execution-workspace').dispatchEvent(new Event('change'));await until(()=>Array.from($('execution-draft').options).some(o=>o.value==='__DRAFT__')&&!$('execution-refresh').disabled,'drafts');
assert($('execution-environment').textContent.includes('Contract Test'),'no live claim');assert($('execution-capabilities').textContent.includes('Meta Ads'),'social capability');
$('execution-draft').value='__DRAFT__';$('execution-draft').dispatchEvent(new Event('change'));$('execution-context').click();await until(()=>!$('execution-policy').hidden&&!$('execution-refresh').disabled,'source context');
const p=__POLICY__;for(const [id,value]of [['execution-total',p.total_cap_micros/1e6],['execution-per-plan',p.per_plan_cap_micros/1e6],['execution-change',p.positive_change_cap_micros/1e6],['execution-actions',p.action_limit],['execution-cooldown',p.cooldown_seconds],['execution-aggressiveness',p.aggressiveness_percent]])$(id).value=value;
$('execution-policy-form').requestSubmit();await until(()=>$('execution-policy-summary').textContent.includes('Total Period Limit')&&!$('execution-refresh').disabled,'saved policy');
assert($('execution-consent').disabled,'separate consent requires explicit acknowledgement');$('execution-consent-check').checked=true;$('execution-consent-check').dispatchEvent(new Event('change'));$('execution-consent').click();await until(()=>!$('execution-configuration').hidden&&!$('execution-refresh').disabled,'consent and named catalog');
assert(!$('execution-social-fields').hidden&&$('execution-google-fields').hidden,'social configuration selector');


const transition='__TRANSITION__', realFetch=window.fetch.bind(window);let release=null;
window.fetch=async(...args)=>{
 const response=await realFetch(...args);
 if(/\/media\/[a-f0-9]{32}$/.test(String(args[0]))){
  assert(response.ok,'actual owned private media read');
  if(transition==='media_integrity'){
   const bytes=new Uint8Array(await response.arrayBuffer());bytes[Math.floor(bytes.length/2)]^=1;
   return new Response(bytes,{status:200,headers:{'Content-Type':response.headers.get('Content-Type')}});
  }
  await new Promise(resolve=>{release=resolve;});
 }
 return response;
};
$('execution-social-catalog').selectedIndex=1;$('execution-social-catalog').dispatchEvent(new Event('change'));
if(transition==='media_session'){
 await until(()=>release!==null,'private media held');
 const token=document.cookie.split(';').map(s=>s.trim()).find(s=>s.startsWith('__Host-inlet_csrf=')).split('=')[1];
 assert((await realFetch('/api/customer/v1/session',{method:'DELETE',headers:{'X-CSRF-Token':token}})).ok,'actual concurrent logout');
 release();await until(()=>$('execution-selection').hidden,'late private media clears old session');
 assert(!$('execution-selection-media').textContent&&!$('execution-review-media').textContent,'no old bytes or summaries survive session change');
 assert($('execution-approve').disabled&&$('execution-start').disabled,'no stale review authority');
}else{
 await until(()=>$('execution-selection-media').textContent.includes('Reviewed media changed.'),'exact byte digest mismatch rejected');
 assert($('execution-prepare').disabled&&!$('execution-selection-media').querySelector('img'),'corrupt private media cannot be reviewed or approved');
 window.fetch=realFetch;$('execution-social-catalog').dispatchEvent(new Event('change'));
 await until(()=>!$('execution-prepare').disabled,'new exact private media review succeeds');
 assert($('execution-selection-media').querySelector('img').naturalWidth>0,'actual supplied image decoded');
}
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',transition})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
