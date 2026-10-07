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

const choices=Array.from($('execution-social-catalog').options).filter(o=>o.value);
assert(choices.length===('__SCENARIO__'==='clarity'?2:1),'historical exact options retained');
if(choices.length===2)assert(choices[0].textContent!==choices[1].textContent,'different historic covers have distinct labels');
const response=await fetch('/api/customer/v1/workspaces/__WORKSPACE__/execution/social/confirmed-configurations?draft_id=__DRAFT__',{credentials:'same-origin',cache:'no-store'});
assert(response.ok,'owned historical configuration read');const configurations=await response.json();
const seen=[],summaries=[],realFetch=window.fetch.bind(window);
window.fetch=async(...args)=>{const r=await realFetch(...args);if(String(args[0]).endsWith('/social/creation-reviews'))seen.push({status:r.status,body:await r.clone().json()});return r;};
for(let index=0;index<choices.length;index++){
 $('execution-social-catalog').value=choices[index].value;$('execution-social-catalog').dispatchEvent(new Event('change'));
 await until(()=>!$('execution-prepare').disabled,'historical private media decoded');
 const selected=configurations.find(row=>row.id===choices[index].value),summary=$('execution-social-summary').textContent;
 assert(selected,'owned selected historical row');const f=selected.configuration;
 for(const ref of [f.identity_id,f.tracking_pixel_id,f.video.sha256.slice(0,12),f.cover.sha256.slice(0,12)])assert(summary.includes(ref),'exact historic identity/pixel/media summary');
 summaries.push(summary);assert($('execution-selection-media').textContent.includes('Exact Private Media Loaded'),'exact selected bytes verified');
 assert($('execution-selection-media').querySelector('video')?.readyState>=2,'historical video playable');
 assert($('execution-selection-media').querySelector('img')?.naturalWidth>0,'historical cover decoded');
 $('execution-prepare').click();await until(()=>seen.length===index+1&&!$('execution-refresh').disabled,'legacy creation denied');
 assert(seen[index].status===409&&seen[index].body.detail==='tiktok_new_custom_identity_creation_unavailable','intentional future creation policy');
 assert($('execution-review').hidden&&$('execution-approve').disabled&&$('execution-start').disabled,'no approvable review or run after denial');
}
if(summaries.length===2)assert(summaries[0]!==summaries[1],'historical cover choices remain visibly distinct');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
