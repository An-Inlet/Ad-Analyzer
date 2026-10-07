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
assert($('execution-budget-kind').value==='daily','legacy daily default');
$('execution-catalog').selectedIndex=1;$('execution-bid').value='0.000001';
$('execution-budget-kind').value='campaign_total_v1';$('execution-budget-kind').dispatchEvent(new Event('change'));
assert($('execution-daily-label').hidden&&!$('execution-campaign-total-label').hidden&&!$('execution-total-guidance').hidden,'explicit total budget input and qualification guidance');
assert($('execution-total-guidance').textContent.includes('4–89')&&$('execution-total-guidance').textContent.includes('Inlet’s supported subset'),'honest qualification subset');
$('execution-campaign-total').value='0.00003';
const realFetch=window.fetch.bind(window);let release=null,requests=[];
window.fetch=async(...args)=>{if(String(args[0]).endsWith('/creation-reviews'))requests.push(JSON.parse(args[1].body));const r=await realFetch(...args);if(String(args[0]).endsWith('/creation-reviews')&&!release){assert(r.ok,'actual total creation API');await new Promise(resolve=>{release=resolve;});}return r;};
$('execution-prepare').click();await until(()=>release!==null,'hold actual total review');
$('execution-budget-kind').value='daily';$('execution-budget-kind').dispatchEvent(new Event('change'));
release();await until(()=>!$('execution-refresh').disabled,'late total review');
assert($('execution-review').hidden&&$('execution-approve').disabled,'budget mode change invalidates pending review');
$('execution-budget-kind').value='campaign_total_v1';$('execution-budget-kind').dispatchEvent(new Event('change'));
$('execution-prepare').click();await until(()=>!$('execution-review').hidden&&!$('execution-refresh').disabled,'exact total creation review');
assert(requests.length===2&&requests.every(r=>r.google.budget_kind==='campaign_total_v1'&&r.google.total_budget_micros===30&&!('daily_budget_micros' in r.google)),'exact discriminated total intent no daily field');
const summary=$('execution-review-summary').textContent;
assert(summary.includes('Campaign Total Budget')&&summary.includes('0.00003')&&!summary.includes('Average Daily Budget'),'exact total amount');
assert(summary.includes('Reserved Upper Bound')&&summary.includes('0.00004')&&summary.includes('Pacific/Pago_Pago'),'reservation stays distinct and account timezone visible');
async function approveStart(){ $('execution-review-check').checked=true;$('execution-review-check').dispatchEvent(new Event('change'));$('execution-approve').click();await until(()=>!$('execution-start').disabled,'approved');$('execution-start').click();await until(()=>$('execution-run-state').textContent.includes('Ready')&&!$('execution-refresh').disabled,'durable run');}
async function advanceTo(state){for(let i=0;i<30;i++){if($('execution-run-state').textContent.includes(state))return;$('execution-advance').click();await until(()=>!$('execution-refresh').disabled,'step completed');}throw new Error('did not reach '+state);}
await approveStart();await advanceTo('Created Paused');
assert($('execution-run-state').textContent.includes('Exposure Reservation Retained'),'creation never releases approved reservation');
const receiptButton=$('execution-steps').querySelector('button');receiptButton.click();await until(()=>$('execution-receipt').textContent.includes('Verified Effect'),'actual durable creation readback');
$('execution-refresh').click();await until(()=>$('execution-run-state').textContent.includes('Created Paused')&&!$('execution-refresh').disabled,'paused run recovered');
$('execution-logout').click();await until(()=>$('execution-message').textContent==='Signed out.','logout');
assert($('execution-review').hidden&&$('execution-runs').hidden&&!$('execution-receipt').textContent,'session cleanup');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
