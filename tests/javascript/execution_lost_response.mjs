const $=id=>document.getElementById(id), assert=(ok,message)=>{if(!ok)throw new Error(message);};
const until=async(test,message)=>{const end=Date.now()+20000;while(!test()){if(Date.now()>end)throw new Error(message+' · '+$('execution-message').textContent);await new Promise(r=>setTimeout(r,20));}};
try{
assert((await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'execution-owner:browser'})})).ok,'actual login');
await import('/app/assets/execution.mjs');await until(()=>$('execution-workspace').options.length===2&&!$('execution-refresh').disabled,'workspaces');
assert($('execution-workspace').textContent.includes('<img src=x>')&&!document.querySelector('img'),'workspace rendered literally');
$('execution-workspace').value='__WORKSPACE__';$('execution-workspace').dispatchEvent(new Event('change'));await until(()=>$('execution-draft').options.length===2&&!$('execution-refresh').disabled,'drafts');
assert($('execution-environment').textContent.includes('Contract Test'),'no live claim');assert($('execution-capabilities').textContent.includes('Meta Ads')&&$('execution-capabilities').textContent.includes('not available'),'honest social blocker');
$('execution-draft').selectedIndex=1;$('execution-draft').dispatchEvent(new Event('change'));$('execution-context').click();await until(()=>!$('execution-policy').hidden&&!$('execution-refresh').disabled,'source context');
const p=__POLICY__;for(const [id,value]of [['execution-total',p.total_cap_micros/1e6],['execution-per-plan',p.per_plan_cap_micros/1e6],['execution-change',p.positive_change_cap_micros/1e6],['execution-actions',p.action_limit],['execution-cooldown',p.cooldown_seconds],['execution-aggressiveness',p.aggressiveness_percent]])$(id).value=value;
$('execution-policy-form').requestSubmit();await until(()=>$('execution-policy-summary').textContent.includes('Total Period Limit')&&!$('execution-refresh').disabled,'saved policy');
assert($('execution-consent').disabled,'separate consent requires explicit acknowledgement');$('execution-consent-check').checked=true;$('execution-consent-check').dispatchEvent(new Event('change'));$('execution-consent').click();await until(()=>!$('execution-configuration').hidden&&!$('execution-refresh').disabled,'consent and named catalog');
assert($('execution-catalog').textContent.includes('Shop Purchases')&&!$('execution-catalog').textContent.includes('customers/'),'named catalog not provider paths');$('execution-catalog').selectedIndex=1;$('execution-daily').value='0.00002';$('execution-bid').value='0.000001';$('execution-prepare').click();await until(()=>!$('execution-review').hidden&&!$('execution-refresh').disabled,'exact creation review');
assert($('execution-review-summary').textContent.includes('Creates Paused Resources'),'creation separate from activation');assert($('execution-start').disabled,'no run before approval');

$('execution-review-check').checked=true;$('execution-review-check').dispatchEvent(new Event('change'));$('execution-approve').click();await until(()=>!$('execution-start').disabled,'exact approval');
const realFetch=window.fetch.bind(window);let admissions=0, admitted=null;
window.fetch=async(...args)=>{
 const response=await realFetch(...args);
 if(String(args[0]).endsWith('/runs')&&args[1]?.method==='POST'){
  admissions++;assert(response.ok,'actual durable admission completed');admitted=await response.clone().json();throw new TypeError('Offline lost admission response');
 }
 return response;
};
$('execution-start').click();await until(()=>$('execution-message').textContent.includes('may have completed')&&!$('execution-refresh').disabled,'lost response reported without false cancellation');
assert(admitted&&admissions===1&&$('execution-start').disabled&&$('execution-review').hidden,'uncertain admission never replays or retains local approval context');
window.fetch=realFetch;
$('execution-refresh').click();await until(()=>$('execution-workspace').options.length===2&&!$('execution-refresh').disabled,'fresh session');
$('execution-workspace').value='__WORKSPACE__';$('execution-workspace').dispatchEvent(new Event('change'));
await until(()=>Array.from($('execution-run').options).some(o=>o.value===admitted.id)&&!$('execution-refresh').disabled,'actual owned run recovered');
$('execution-run').value=admitted.id;$('execution-run').dispatchEvent(new Event('change'));
await until(()=>$('execution-run-state').textContent.includes('Ready')&&!$('execution-refresh').disabled,'exact admitted run selected without replay');
assert(location.pathname.endsWith('/'+admitted.id)&&admissions===1,'durable identity recovered');
assert($('execution-policy').hidden&&$('execution-configuration').hidden&&$('execution-review').hidden,'recovery does not resurrect unrelated proposal or approval');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
