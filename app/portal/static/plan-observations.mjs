// Historical payload checks only. The server owns facts/action proof and authorization.
const positive=v=>Number.isSafeInteger(v)&&v>0;
const string=(v,max)=>typeof v==='string'&&v.length>0&&v.length<=max;
const key=v=>typeof v==='string'&&/^[a-z][a-z0-9_:-]{0,95}$/.test(v);
const digest=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const numeric=v=>typeof v==='string'&&/^[0-9]{1,32}$/.test(v);
// API timestamps preserve microseconds; Date.parse alone rounds and normalizes bad dates.
const instant=v=>{
  if(typeof v!=='string')return null;
  const m=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|([+-])(\d{2}):(\d{2}))$/.exec(v);
  if(!m)return null;
  const [year,month,day,hour,minute,second]=m.slice(1,7).map(Number);
  if(year<1||month<1||month>12||day<1||hour>23||minute>59||second>59)return null;
  const ms=Date.parse(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`),d=new Date(ms);
  if(!Number.isFinite(ms)||d.getUTCFullYear()!==year||d.getUTCMonth()+1!==month||d.getUTCDate()!==day)return null;
  const offsetHours=Number(m[10]??0),offsetMinutes=Number(m[11]??0);
  if(offsetHours>23||offsetMinutes>59)return null;
  const offset=(offsetHours*60+offsetMinutes)*60*(m[9]==='-'?-1:1);
  return BigInt(ms)*1000n+BigInt((m[7]??'').padEnd(6,'0'))-BigInt(offset)*1000000n;
};
const time=v=>instant(v)!==null;
const platforms=['google_ads','meta_ads','tiktok_ads'];
const accountFields=['workspace_id','account_id','connection_id','platform','connection_version'];
const exact=(v,keys)=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const account=v=>exact(v,accountFields)&&positive(v.workspace_id)&&positive(v.account_id)&&positive(v.connection_id)&&platforms.includes(v.platform)&&string(v.connection_version,160);
const sameAccount=(a,b)=>account(a)&&account(b)&&accountFields.every(k=>a[k]===b[k]);
const fail=()=>{throw Error('The observation history response could not be verified. Read it again when ready.');};
const fields={delivery_status:'Delivery Status',landing_page:'Landing Page',country_targets:'Country Targets'};
export const observationLabels={matching:'Observed Match — Supported Fields Only',partial:'Observed Partial Match',conflicting:'Observed Conflict',unavailable:'Observation Unavailable'};
function value(v){
  if(!exact(v,['field','value']))return false;
  if(v.field==='delivery_status')return ['enabled','paused'].includes(v.value);
  if(v.field==='landing_page')return string(v.value,2048)&&/^https:\/\/[^\s]+$/.test(v.value);
  if(v.field==='country_targets')return Array.isArray(v.value)&&v.value.length>0&&v.value.length<=50&&v.value.every(c=>typeof c==='string'&&/^[A-Z]{2}$/.test(c));
  return false;
}
function evidence(e,event){
  const s=e?.source,t=e?.target,r=t?.provider_reference;
  if(!exact(e,['source','target'])||!exact(s,['key','workspace_id','kind','account','document_schema','document_digest','source_binding_digest','source_revision','privacy_revision','reporting_window','observation_started_at','observed_at','expires_at','coverage','declared_scope','reasons','metric_basis'])||!exact(t,['account','provider_reference','canonical_entity_key','selection_key','catalog_evidence_key','kind','display_name','budget_owner_key'])||!exact(r,['platform','advertiser_id','entity_id','parent_campaign_id']))fail();
  if(!s||!t||!r||s.workspace_id!==event.workspace_id||!sameAccount(s.account,t.account)||s.account.workspace_id!==event.workspace_id||s.kind!=='native_catalog'||!['complete_in_declared_scope','partial'].includes(s.coverage)||!key(s.key)||s.key!==t.catalog_evidence_key||!string(s.document_schema,160)||!digest(s.document_digest)||!digest(s.source_binding_digest)||!string(s.source_revision,160)||!Number.isSafeInteger(s.privacy_revision)||s.privacy_revision<0||!string(s.declared_scope,2000)||!string(s.metric_basis,2000)||!Array.isArray(s.reasons)||s.reasons.length>20||s.reasons.some(v=>!key(v))||new Set(s.reasons).size!==s.reasons.length||(s.coverage==='partial'&&!s.reasons.length))fail();
  if(!digest(t.canonical_entity_key)||!digest(t.selection_key)||(t.budget_owner_key!==null&&!digest(t.budget_owner_key))||(t.display_name!==null&&!string(t.display_name,160))||!['campaign',s.account.platform==='meta_ads'?'adset':'adgroup'].includes(t.kind)||r.platform!==s.account.platform||!numeric(r.advertiser_id)||!numeric(r.entity_id)||(r.platform==='google_ads'&&r.advertiser_id.length!==10)||((t.kind==='campaign')!==(r.parent_campaign_id===null))||(t.kind!=='campaign'&&!numeric(r.parent_campaign_id)))fail();
  if(![s.observation_started_at,s.observed_at,s.expires_at].every(time)||instant(s.observation_started_at)>instant(s.observed_at)||instant(s.observed_at)>instant(event.observed_at)||instant(event.observed_at)>=instant(s.expires_at))fail();
  if(s.reporting_window!==null){const w=s.reporting_window;if(!exact(w,['starts_at','ends_at_exclusive'])||![w.starts_at,w.ends_at_exclusive].every(time)||instant(w.starts_at)>=instant(w.ends_at_exclusive)||instant(w.ends_at_exclusive)>instant(s.observation_started_at)||instant(w.ends_at_exclusive)-instant(w.starts_at)>400n*86400n*1000000n)fail();}
}
export function validateObservation(e){
  const keys=['advertising_writes_enabled','spending_authority','workspace_id','plan_id','version','document_digest','action_key','action_digest','event_id','observed_at','status','comparisons','limitations','causality','applied_by'];
  if(!exact(e,keys)||!time(e.observed_at)||e.causality!=='not_assessed'||e.applied_by!==null||!Object.hasOwn(observationLabels,e.status)||!Array.isArray(e.comparisons)||e.comparisons.length>20||!Array.isArray(e.limitations)||e.limitations.length<1||e.limitations.length>20||e.limitations.some(v=>!string(v,2000)))fail();
  const seen=new Set();let observed=0,conflict=false;
  for(const c of e.comparisons){
    if(!exact(c,['proposal_key','expected','observed','evidence','unavailable_reason'])||!key(c.proposal_key)||seen.has(c.proposal_key)||!value(c.expected))fail();
    seen.add(c.proposal_key);
    if(c.observed===null){if(!string(c.unavailable_reason,2000))fail();if(c.evidence!==null)evidence(c.evidence,e);}
    else{
      if(!value(c.observed)||c.expected.field!==c.observed.field||c.unavailable_reason!==null)fail();
      evidence(c.evidence,e);observed++;
      if(JSON.stringify(c.expected.value)!==JSON.stringify(c.observed.value))conflict=true;
    }
  }
  const status=!observed?'unavailable':conflict?'conflicting':observed<e.comparisons.length?'partial':'matching';
  if(e.status!==status)fail();
}
export function appendObservation(item,e,text,stamp){
  item.append(text('p',`Observation Compared At: ${stamp(e.observed_at)}`),text('p','Matching fields do not establish implementation, who made a change, change time, delivery or business lift. Causality Not Assessed.'));
  for(const c of e.comparisons){
    const format=v=>Array.isArray(v.value)?v.value.join(', '):v.value;
    item.append(text('h4',`${fields[c.expected.field]} · Proposal ${c.proposal_key}`),text('p',`Expected: ${format(c.expected)}`),text('p',c.observed===null?`Unavailable: ${c.unavailable_reason}`:`Observed: ${format(c.observed)}`));
    if(c.evidence!==null){const s=c.evidence.source,t=c.evidence.target,r=t.provider_reference;
      item.append(text('p',`Historical Source Interval: ${stamp(s.observation_started_at)} to ${stamp(s.observed_at)} · Evidence Expiry: ${stamp(s.expires_at)}`),text('p',`Source: ${s.document_schema} · Revision ${s.source_revision} · Coverage ${s.coverage} · ${s.declared_scope}`),text('p',`Account ${s.account.account_id} · Connection ${s.account.connection_id} · Generation ${s.account.connection_version} · Privacy Revision ${s.privacy_revision}`),text('p',`Target: ${t.display_name??'Name Unavailable'} · ${r.platform} · ${t.kind} ${r.entity_id} · Provider Account ${r.advertiser_id} · Parent ${r.parent_campaign_id??'None'}`),text('p',`Source Digest: ${s.document_digest} · Binding Digest: ${s.source_binding_digest}`),text('p',`Metric Basis: ${s.metric_basis}`));
      for(const reason of s.reasons)item.append(text('p',`Source Limitation: ${reason}`));
    }
  }
  for(const limitation of e.limitations)item.append(text('p',limitation));
  item.append(text('p','Historical values, not a current-state check. Source authenticity and original action binding require server verification; this view does not recompute their digests.'));
}
