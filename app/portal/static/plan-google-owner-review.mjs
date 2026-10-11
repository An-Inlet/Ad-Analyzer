import {ownerAmount} from './plan-google-owner-inputs.mjs';
// Saved immutable proof only. No discovery, mutation or native-edit qualification.
export function appendGoogleOwnerReview(host,plan){
 const proof=plan.google_budget_owner_review;if(proof===null||proof===undefined)return;
 if(plan.policy_version!=='inlet.descriptive-review.v6'||plan.generator_version!=='inlet.descriptive-planning.v6'||proof.schema_version!=='inlet.google-budget-owner-review-proof.v1'||proof.advertising_writes_enabled!==false||proof.spending_authority!=='none'||!Array.isArray(proof.reviews)||proof.reviews.length>20||!Array.isArray(plan.google_budget_input_catalogs))throw Error('Saved owner review unavailable.');
 const doc=host.ownerDocument,node=(tag,value)=>{const n=doc.createElement(tag);n.textContent=String(value);return n;},section=node('section','');section.id='google-owner-review';
 section.append(node('h3','Shared Google Daily Setting Review'),node('p','These are saved observations and customer hypotheses. Daily settings are separate from period allocations. Inlet will not apply these changes.'));
 if(!proof.reviews.length)section.append(node('p','No shared daily setting reviews were included in this version.'));
 for(const review of proof.reviews){
  const w=review.witness,i=review.intent;if(review.disposition!=='investigate_only'||review.application!=='unavailable'||review.period_spending_compatibility!=='not_assessed'||review.provider_edit_validity!=='not_assessed'||!w||!i||!Array.isArray(w.affected_campaigns)||w.affected_campaigns.length<2||w.affected_campaigns.length>200)throw Error('Saved owner review unavailable.');
  const block=node('section',''),scenario=plan.inputs.scenario_intents.find(s=>s.key===i.scenario_key),account=w.representative?.account;
  if(!scenario||!account||account.workspace_id!==plan.inputs.workspace_id||account.account_id!==i.account_id||account.platform!=='google_ads'||i.currency!==w.currency||!/^[A-Z]{3}$/.test(w.currency)||!plan.google_budget_input_catalogs.some(c=>JSON.stringify(c)===JSON.stringify(w.catalog_evidence)))throw Error('Saved owner review scope unavailable.');
  const evidence=w.catalog_evidence.reference,times=[evidence.observation_started_at,evidence.observed_at,evidence.expires_at].map(Date.parse);
  if(!times.every(Number.isFinite)||times[0]>times[1]||times[1]>=times[2]||w.affected_campaigns.some(m=>JSON.stringify(m.account)!==JSON.stringify(account)||m.budget_owner_key!==w.representative.budget_owner_key))throw Error('Saved owner review observations unavailable.');
  block.append(node('h4',scenario.title),node('p',`Observed Daily Setting: ${w.currency} ${ownerAmount(w.current_amount_micros)} Per Day`),node('p',`Requested Daily Hypothesis: ${i.currency} ${ownerAmount(i.requested_amount_micros)} Per Day`),node('p',i.requested_amount_micros===0?'Manual Review Required. Zero is not a qualified native edit or a guarantee of zero exposure.':'Review Required — Not Qualified Against The Period Ceiling'));
  const list=node('ul','');list.dataset.role='owner-members';for(const m of w.affected_campaigns)list.append(node('li',m.display_name??'Campaign Name Unavailable'));block.append(node('h4','All Affected Campaigns'),list);
  block.append(node('p',`Observed ${evidence.observation_started_at} to ${evidence.observed_at}. Original evidence expires ${evidence.expires_at}.`));section.append(block);
 }
 host.append(section);
}
