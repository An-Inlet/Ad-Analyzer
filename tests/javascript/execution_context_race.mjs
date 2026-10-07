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
$('execution-social-catalog').selectedIndex=1;$('execution-social-catalog').dispatchEvent(new Event('change'));
assert($('execution-social-summary').textContent.includes('Offline Profile')&&$('execution-social-summary').textContent.includes('Confirmed'),'exact saved configuration summary');


const realFetch=window.fetch.bind(window), transition='__TRANSITION__';
let release=null, delayed=null;
window.fetch=async(...args)=>{
 const response=await realFetch(...args);
 if(String(args[0]).endsWith('/social/creation-reviews')&&!release){
  assert(response.ok,'actual delayed review success');
  delayed=await response.clone().json();
  if(transition==='body'){
   const parse=response.json.bind(response);
   response.json=async()=>{const value=await parse();await new Promise(resolve=>{release=resolve;});return value;};
  }else await new Promise(resolve=>{release=resolve;});
  if(transition==='failure')return new Response(JSON.stringify({detail:'old session failure'}),{status:401,headers:{'Content-Type':'application/json'}});
  if(transition==='lost')throw new TypeError('Offline simulated lost response');
 }
 return response;
};
await until(()=>!$('execution-prepare').disabled,'exact selected media ready');$('execution-prepare').click();await until(()=>release!==null,'real review response held');
assert($('execution-social-catalog').options.length===3,'two persisted confirmed configurations');
const before=$('execution-social-catalog').value;
if(['race','body','aba','failure','lost'].includes(transition)){
 $('execution-social-catalog').selectedIndex=2;$('execution-social-catalog').dispatchEvent(new Event('change'));
 assert($('execution-social-catalog').value!==before,'selected configuration changed while prepare pending');
 if(transition==='aba'){$('execution-social-catalog').value=before;$('execution-social-catalog').dispatchEvent(new Event('change'));}
}else if(transition==='draft'){
 $('execution-draft').value='';$('execution-draft').dispatchEvent(new Event('change'));
}else if(transition==='workspace'){
 $('execution-workspace').value='';$('execution-workspace').dispatchEvent(new Event('change'));
}else if(transition==='logout'){
 $('execution-logout').click();assert($('execution-selection').hidden,'logout immediately hides the old customer context');
}else if(transition==='session'){
 const token=document.cookie.split(';').map(s=>s.trim()).find(s=>s.startsWith('__Host-inlet_csrf=')).split('=')[1];
 assert((await realFetch('/api/customer/v1/session',{method:'DELETE',headers:{'X-CSRF-Token':token}})).ok,'real concurrent session ended');
}else if(transition==='policy'){
 $('execution-total').value='99';$('execution-total').dispatchEvent(new Event('input'));
}else if(transition==='run'){
 $('execution-run').selectedIndex=1;$('execution-run').dispatchEvent(new Event('change'));
}
release();await until(()=>!$('execution-refresh').disabled,'delayed review resolved');
assert($('execution-review').hidden&&$('execution-approve').disabled&&$('execution-start').disabled,'late configuration A review must not become approvable after selecting B');
assert(!$('execution-review-check').checked,'stale exact acknowledgement cleared');
window.fetch=realFetch;
if(['failure','lost'].includes(transition))assert(!$('execution-selection').hidden,'late failure never clears the new selection or signs out its context');
if(['race','body','aba','failure','lost'].includes(transition)){
 await until(()=>!$('execution-prepare').disabled,'current media loaded');$('execution-prepare').click();await until(()=>!$('execution-review').hidden&&!$('execution-refresh').disabled,'fresh current review');
 assert($('execution-start').disabled,'fresh current review requires its own exact approval');
}else if(['logout','session'].includes(transition)){
 assert($('execution-selection').hidden&&!$('execution-review-media').textContent,'session transition clears customer data and private previews');
 assert((await realFetch('/api/customer/v1/session')).status===401,'session actually ended');
}else if(transition==='policy')assert($('execution-consent').disabled&&$('execution-configuration').hidden,'edited policy invalidates consent context');
else if(transition==='run')assert($('execution-policy').hidden&&$('execution-configuration').hidden,'run recovery clears unrelated proposal and configuration');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed',transition})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
