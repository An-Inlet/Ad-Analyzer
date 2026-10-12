// Historical fixture findings only. This renderer never establishes current reliance.
import {instant} from './plan-observations.mjs';
const observed='inlet.google-budget-observation.v1',invalidated='inlet.google-budget-invalidation.v1';
const digest=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const id=v=>typeof v==='string'&&/^[a-f0-9]{32}$/.test(v);
const positive=v=>Number.isSafeInteger(v)&&v>0;
const time=v=>instant(v)!==null;
const noAuthority=v=>v?.advertising_writes_enabled===false&&v?.spending_authority==='none';
const accountFields=['workspace_id','account_id','connection_id','connection_version','platform'];
const sameAccount=(a,b)=>a&&b&&accountFields.every(k=>a[k]===b[k]);
const base=['advertising_writes_enabled','spending_authority','workspace_id','plan_id','version','document_digest','action_key','action_digest','event_id','actor_id','recorded_at','provenance','current_reliance','implementation','schema_version'];
const same=(a,b)=>['workspace_id','plan_id','version','document_digest','action_key','action_digest'].every(k=>a?.[k]===b?.[k]);
const fail=()=>{throw Error('The historical budget evidence could not be verified.');};
export const isBudgetEvent=e=>e?.schema_version===observed||e?.schema_version===invalidated;
export function validateBudgetEvent(e){
  const extra=e.schema_version===observed?['comparison','proof','finding']:['observation_event_id','observation_digest','observation_sequence','observation_recorded_at','reason','original_source_digest','current_account','current_source_digest','privacy_revision'];
  if(!isBudgetEvent(e)||Object.keys(e).length!==base.length+extra.length||[...base,...extra].some(k=>!Object.hasOwn(e,k))||!id(e.actor_id)||!time(e.recorded_at)||e.provenance!=='injected_fixture'||e.current_reliance!=='not_assessed'||e.implementation!=='not_assessed')fail();
  if(e.schema_version===invalidated){
    if(!id(e.observation_event_id)||e.observation_event_id===e.event_id||!digest(e.observation_digest)||!positive(e.observation_sequence)||e.reason!=='source_generation_changed'||!digest(e.original_source_digest)||!digest(e.current_source_digest)||e.original_source_digest===e.current_source_digest||e.current_account?.workspace_id!==e.workspace_id||e.current_account?.account?.platform!=='google_ads'||!Number.isSafeInteger(e.privacy_revision)||e.privacy_revision<0)fail();
    if(!time(e.observation_recorded_at)||instant(e.observation_recorded_at)>instant(e.recorded_at))fail();
    return;
  }
  const c=e.comparison,p=e.proof,t=p?.ticket,f=c?.fresh;
  if(!['matches_hypothesis','differs_from_hypothesis'].includes(e.finding)||c?.schema_version!=='inlet.google-daily-budget-hypothesis-comparison.v1'||c.application!=='unavailable'||c.causality!=='not_assessed'||c.provider_edit_validity!=='not_assessed'||c.period_spending_compatibility!=='not_assessed'||c.integrity!=='clear'||c.advertising_writes_enabled!==false||c.spending_authority!=='none'||!same(e,c.binding)||c.compared_at!==e.recorded_at||p?.schema_version!=='inlet.google-budget-read-proof.v1'||!same(e,t?.binding)||t.provenance!=='injected_fixture'||t.api_version!=='v22'||!digest(t.profile_digest)||!Array.isArray(p.pages)||p.pages.length<3||p.pages.length>30||f?.atomic_snapshot!==false||f?.representative?.account?.workspace_id!==e.workspace_id||t.account?.workspace_id!==e.workspace_id)fail();
  const reviews=c.document?.google_budget_owner_review?.reviews;
  const r=Array.isArray(reviews)?reviews.filter(v=>v.action_key===e.action_key):[];
  if(r.length!==1||r[0].application!=='unavailable'||!Number.isSafeInteger(r[0].intent?.requested_amount_micros)||!Number.isSafeInteger(f.current_amount_micros)||r[0].intent.requested_amount_micros<0||f.current_amount_micros<0||((r[0].intent.requested_amount_micros===f.current_amount_micros)!==(e.finding==='matches_hypothesis')))fail();
  const d=c.document,ref=f.catalog_evidence?.reference,cat=f.catalog_evidence?.catalog,n=cat?.native_observation,m=cat?.metadata_observation,a=ref?.account;
  if(!noAuthority(d)||!noAuthority(p)||!noAuthority(t)||!noAuthority(f)||!noAuthority(cat)||!noAuthority(n)||d.inputs?.workspace_id!==e.workspace_id||d.inputs?.plan_id!==e.plan_id||d.version!==e.version||f.schema_version!=='inlet.google-daily-budget-owner-witness.v1'||cat?.schema_version!=='inlet.planning-target-catalog.v2'||n?.schema_version!=='inlet.planning-target-catalog.v1'||m?.schema_version!=='inlet.planning-entity-metadata.v1'||!sameAccount(a,f.representative.account)||a?.workspace_id!==e.workspace_id||a?.platform!=='google_ads'||t.account?.account?.account_id!==a.account_id||t.account.account.connection_id!==a.connection_id||t.account.account.platform!==a.platform||t.account.connection_version!==a.connection_version||ref.source_revision!==a.connection_version||ref.source_binding_digest!==c.source_binding_digest||c.privacy_revision!==ref.privacy_revision||t.privacy_revision!==ref.privacy_revision||!Number.isSafeInteger(c.privacy_revision)||c.privacy_revision<0)fail();
  if([n,m].some(v=>!sameAccount(a,v)||v.source_binding_digest!==ref.source_binding_digest||v.atomic_snapshot!==false)||ref.workspace_id!==e.workspace_id||ref.document_digest!==cat.composite_digest||n.inventory_digest!==m.native_inventory_digest||f.currency!==n.currency||f.cadence!=='daily'||f.unit!=='micros'||f.owner_key!==r[0].witness?.owner_key)fail();
  if(!sameAccount(a,r[0].witness?.representative?.account)||r[0].witness?.catalog_evidence?.reference?.source_binding_digest!==c.source_binding_digest||r[0].witness.catalog_evidence.reference.privacy_revision!==c.privacy_revision)fail();
  const times=[d.generated_at,t.prepared_at,ref.observation_started_at,ref.observed_at,c.compared_at,ref.expires_at,t.expires_at];
  if(!times.every(time)||instant(d.generated_at)>instant(t.prepared_at)||instant(t.prepared_at)>instant(ref.observation_started_at)||instant(ref.observation_started_at)>instant(ref.observed_at)||instant(ref.observed_at)>instant(c.compared_at)||instant(c.compared_at)>=instant(ref.expires_at)||instant(ref.expires_at)!==instant(t.expires_at))fail();
  for(const v of [n,m])if(![v.observation_started_at,v.observed_at,v.expires_at].every(time)||instant(v.observation_started_at)!==instant(ref.observation_started_at)||instant(v.observed_at)!==instant(ref.observed_at)||instant(v.expires_at)!==instant(ref.expires_at))fail();
}
export function budgetEventLabel(e){return e.schema_version===invalidated?'Historical Budget Evidence Invalidated':e.finding==='matches_hypothesis'?'Historical Budget Setting Matches Hypothesis':'Historical Budget Setting Differs From Hypothesis';}
export function appendBudgetEvent(item,e,text,stamp){
  item.append(text('p',`Recorded ${stamp(e.recorded_at)}`),text('p','Injected Fixture Evidence — Not A Live Provider Verification'),text('p','Historical finding only. Current reliance is not assessed; later invalidations may appear on another page. This does not establish who changed a setting, implementation, spending-limit compliance, or results.'));
  if(e.schema_version===invalidated)item.append(text('p',`Source generation changed. Invalidates event ${e.observation_sequence} (${e.observation_event_id}); the original record remains in history.`));
  else item.append(text('p','Comparison covers the average daily budget setting in account currency. Application remains unavailable.'));
}
