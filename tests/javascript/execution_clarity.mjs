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
assert(choices.length===2&&choices[0].textContent!==choices[1].textContent,'distinct owned Page/Pixel configurations must have distinct readable option labels');

const seen=[];const realFetch=window.fetch.bind(window);
window.fetch=async(...args)=>{const r=await realFetch(...args);if(String(args[0]).endsWith('/social/creation-reviews')&&r.ok)seen.push(await r.clone().json());return r;};
const summaries=[];
for(let index=1;index<=2;index++){
 $('execution-social-catalog').selectedIndex=index;$('execution-social-catalog').dispatchEvent(new Event('change'));
 await until(()=>!$('execution-prepare').disabled,'exact selected private media loaded');
 summaries.push($('execution-social-summary').textContent);
 assert($('execution-selection-media').textContent.includes('Exact Private Media Loaded'),'selection bytes verified and decoded');
 $('execution-prepare').click();await until(()=>!$('execution-review').hidden&&!$('execution-refresh').disabled,'exact review media loaded');
 const f=seen.at(-1).configuration, summary=$('execution-review-summary').textContent;
 for(const ref of f.image?[f.page_id,f.pixel_id,f.image.sha256.slice(0,12)]:[f.identity_id,f.tracking_pixel_id,f.video.sha256.slice(0,12),f.cover.sha256.slice(0,12)]){
  assert(summary.includes(ref)&&summaries.at(-1).includes(ref),'owned identity/measurement/media appears in selection and exact review');
 }
 assert($('execution-review-media').textContent.includes('Exact Private Media Loaded'),'review bytes verified and decoded');
 const images=Array.from($('execution-review-media').querySelectorAll('img'));
 assert(images.length===1&&images[0].naturalWidth>0&&images[0].src.startsWith('blob:'),'actual private image or cover visibly loaded');
 if(f.cover)assert($('execution-review-media').querySelector('video')?.readyState>=2,'actual private video decoded');
}
assert(summaries[0]!==summaries[1],'different identity or cover visibly distinguished');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
