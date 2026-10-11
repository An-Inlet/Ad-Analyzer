import {renderGoogleOwnerInputs} from './plan-google-owner-inputs.mjs';
import {appendGoogleOwnerReview} from './plan-google-owner-review.mjs';
const host=document.getElementById('host'),assert=(value,message)=>{if(!value)throw Error(message);};
try{
 const response=await fetch('/owner-duplicate-plan.json');assert(response.ok,'genuine saved DTO');const plan=await response.json();
 appendGoogleOwnerReview(host,plan);
 const labels=[...host.querySelectorAll('[data-role="owner-members"] li')].map(n=>n.textContent);
 assert(JSON.stringify(labels)===JSON.stringify(['Mug <img src=x> · Campaign 1','Mug <img src=x> · Campaign 2']),'duplicate names must show distinct actual campaign IDs');
 assert(!host.querySelector('img,script'),'literal campaign names must remain text');
 // Synthetic current component response derived from genuine member identities.
 // It is not an authenticated acquisition; the saved historical DTO stays untouched.
 const review=plan.google_budget_owner_review.reviews[0],w=review.witness,a=w.representative.account;
 const expires=new Date(Date.now()+60000).toISOString(),catalog=structuredClone(w.catalog_evidence.catalog);catalog.expires_at=expires;
 const option={...structuredClone(w),account_id:a.account_id,owner_selection_id:review.intent.owner_selection_id,expected_observation_digest:review.intent.expected_observation_digest,expected_owner_facts_digest:review.intent.expected_owner_facts_digest,expires_at:expires,review_only:true,economic_qualification:'not_assessed',advertising_writes_enabled:false,spending_authority:'none'};
 const context={catalogs:[{account:{id:a.account_id,name:'Google',platform:'google_ads'},catalog}],reportingWindow:plan.inputs.reporting_window,currency:w.currency,totalCeilingMicros:plan.inputs.total_ceiling_micros,scenarios:plan.inputs.scenario_intents.map(x=>({...x,allocations:x.allocations.map(row=>({...row,target:{account_id:a.account_id,canonical_entity_key:row.target.canonical_entity_key,selection_key:row.target.selection_key}}))})),exclusions:[]};
 const input=document.createElement('div');document.body.append(input);
 const capability={schema_version:'inlet.planning-capabilities.v1',workspace_id:a.workspace_id,policy_version:plan.policy_version,generator_version:plan.generator_version,selected_reporting_available:true,advertising_writes_enabled:false,spending_authority:'none'};
 const handle=renderGoogleOwnerInputs(input,{capability,workspaceId:a.workspace_id,context:()=>context,current:()=>{},discover:async()=>({account_id:a.account_id,status:'available',reason:null,owners:[option],advertising_writes_enabled:false,spending_authority:'none'})});
 const role=name=>input.querySelector(`[data-role="${name}"]`),tick=()=>new Promise(resolve=>setTimeout(resolve,0));
 role('owner-discover').click();await tick();
 const choice=role('owner-option');assert(choice,'current synthetic option present');
 assert(choice.options[1].textContent===labels.join(' · '),'owner option preserves both distinct IDs');
 choice.value='0';choice.dispatchEvent(new Event('change'));
 assert(JSON.stringify([...input.querySelectorAll('[data-role="owner-members"] li')].map(x=>x.textContent))===JSON.stringify(labels),'selected detail exact member labels');
 role('owner-scenario').value=review.intent.scenario_key;role('owner-requested').value='0';role('owner-include').click();await tick();
 assert(handle.readIntents().length===1,'explicit component inclusion');
 assert([...input.querySelectorAll('[data-role="owner-members"]')].every(list=>JSON.stringify([...list.children].map(x=>x.textContent))===JSON.stringify(labels)),'included member labels retain both identities');
 assert(!input.querySelector('img,script'),'input labels stay literal');handle.clear();

 for(const id of [null,'', 'x', '1'.repeat(33)]){
  const broken=structuredClone(plan);broken.google_budget_owner_review.reviews[0].witness.affected_campaigns[1].provider_reference.entity_id=id;
  let refused=false;try{appendGoogleOwnerReview(document.createElement('div'),broken);}catch{refused=true;}
  assert(refused,'malformed native reference must fail closed');
 }
 const missing=structuredClone(plan);delete missing.google_budget_owner_review.reviews[0].witness.affected_campaigns[1].provider_reference;
 let refused=false;try{appendGoogleOwnerReview(document.createElement('div'),missing);}catch{refused=true;}
 assert(refused,'missing native reference must fail closed');
 const fallback=structuredClone(plan);fallback.google_budget_owner_review.reviews[0].witness.affected_campaigns[0].display_name=null;
 const fallbackHost=document.createElement('div');appendGoogleOwnerReview(fallbackHost,fallback);
 assert(fallbackHost.querySelector('li').textContent==='Campaign Name Unavailable · Campaign 1','existing missing-name fallback retains actual identity');
 await fetch('/result',{method:'POST',body:'PASS'});
}catch(error){await fetch('/result',{method:'POST',body:error.stack||String(error)});}
