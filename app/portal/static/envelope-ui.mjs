// Read-only native settings, never a financial bound or an execution approval.
const reasons={original_total_creation_unavailable:'The original total-budget creation is unavailable.',original_receipt_unavailable:'Original completion evidence is unavailable.',native_inventory_incomplete:'The account inventory could not be verified completely.',native_resource_unavailable:'The original campaign or budget is unavailable.',native_budget_changed:'The current native budget differs from the original configuration.',native_ownership_changed:'The budget ownership or sharing changed.',native_campaign_changed:'The campaign configuration or schedule changed.',financial_basis_unqualified:'These settings do not establish a financial spending bound.',historical_liabilities_unverified:'Earlier financial liabilities have not been verified.'};
const fields=['schema_version','run_id','environment','status','quantity','currency','time_zone','campaign_starts_at','campaign_ends_at','original_total_micros','observed_total_micros','reservation_micros','reservation_state','original_binding_digest','inventory_digest','observation_started_at','observed_at','expires_at','reasons','financial_basis','financial_upper_micros','spending_authority','settlement','outside_writer_prevention','portfolio_coverage'];
const fail=()=>{throw Error('This budget observation could not be verified. Read it again.');};
const money=v=>Number.isSafeInteger(v)&&v>=0&&v<=1e15;
const timestamp=v=>typeof v==='string'&&/(Z|[+-]\d\d:\d\d)$/.test(v)&&Number.isFinite(Date.parse(v));
export function checkedEnvelope(v,run,now=Date.now()){
 if(!v||Object.keys(v).length!==fields.length||!fields.every(k=>Object.hasOwn(v,k))||v.schema_version!=='inlet.google-total-envelope-observation.v1'||v.run_id!==run.id||!['contract_test','live'].includes(v.environment)||v.environment!==run.environment||!['matching_configuration','configuration_drift','unavailable'].includes(v.status)||v.quantity!=='native_campaign_total_budget_setting_micros'||!/^\w{3}$/.test(v.currency)||!/^[A-Z]{3}$/.test(v.currency)||typeof v.time_zone!=='string'||v.time_zone.length>64||![v.original_total_micros,v.reservation_micros].every(money)||(v.observed_total_micros!==null&&!money(v.observed_total_micros))||!['held','settled','superseded'].includes(v.reservation_state)||![v.original_binding_digest,v.inventory_digest].every(x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x))||![v.campaign_starts_at,v.campaign_ends_at,v.observation_started_at,v.observed_at,v.expires_at].every(timestamp))fail();
 try{new Intl.DateTimeFormat('en',{timeZone:v.time_zone});}catch{fail();}
 if(Date.parse(v.campaign_starts_at)>=Date.parse(v.campaign_ends_at)||Date.parse(v.observation_started_at)>Date.parse(v.observed_at)||Date.parse(v.observed_at)>now||Date.parse(v.expires_at)<=now||Date.parse(v.expires_at)<=Date.parse(v.observed_at)||v.financial_basis!=='unqualified'||v.financial_upper_micros!==null||v.spending_authority!=='none'||v.settlement!=='not_assessed'||v.outside_writer_prevention!=='not_asserted'||v.portfolio_coverage!=='single_original_run_only'||!Array.isArray(v.reasons)||v.reasons.length<2||v.reasons.length>9||new Set(v.reasons).size!==v.reasons.length||!v.reasons.every(x=>Object.hasOwn(reasons,x))||!['financial_basis_unqualified','historical_liabilities_unverified'].every(x=>v.reasons.includes(x))||(v.status==='matching_configuration'?(v.observed_total_micros!==v.original_total_micros||v.reasons.length!==2):v.reasons.length===2))fail();return v;
}
export function envelopeUI({api,guarded,state,clock=Date.now,monitor=fn=>setInterval(fn,500)}){
 const $=name=>document.getElementById('envelope-'+name);
 const cookie=()=>document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('__Host-inlet_csrf='))||'';
 const key=()=>JSON.stringify([state().workspace,state().signed,state().run?.id,state().run?.environment,cookie()]);
 let epoch=0,shown=null,shownKey='',watchedKey=key();
 const node=(tag,value)=>{const e=document.createElement(tag);e.textContent=String(value);return e;};
 function reset(){epoch++;watchedKey=key();shown=null;shownKey='';$('result').hidden=true;$('summary').replaceChildren();$('reasons').replaceChildren();$('notice').textContent='';}
 function current(){if(key()!==watchedKey){reset();return;}if(shown&&(key()!==shownKey||Date.parse(shown.expires_at)<=clock())){reset();$('notice').textContent='The observation is no longer current. Read it again.';}}
 function enable(busy){current();const s=state();$('section').hidden=!s.signed||!s.workspace||!s.run;$('read').disabled=busy||!s.signed||!s.workspace||!s.run;}
 const amount=(value,currency)=>value===null?'Unavailable':`${currency} ${(value/1e6).toLocaleString('en-US',{maximumFractionDigits:6})}`;
 $('read').onclick=()=>guarded(async()=>{
  reset();const initial=key(),ticket=epoch,s=state(),run={...s.run};
  try{
   const result=await api(`/workspaces/${encodeURIComponent(s.workspace)}/execution/runs/${encodeURIComponent(run.id)}/envelope-observation`,'POST');
   if(ticket!==epoch||initial!==key())return;
   const v=checkedEnvelope(result,run,clock());shown=v;shownKey=initial;
   const labels={matching_configuration:'Observed Settings Match The Original',configuration_drift:'Observed Settings Have Changed',unavailable:'Current Settings Are Unavailable'};
   $('notice').textContent=labels[v.status];$('result').hidden=false;
   const rows=[['Environment',v.environment==='contract_test'?'Offline Contract Test':'Live Account Read'],['Original Native Campaign Total',amount(v.original_total_micros,v.currency)],['Observed Native Campaign Total',amount(v.observed_total_micros,v.currency)],['Recorded Reservation — Separate Allocation',amount(v.reservation_micros,v.currency)],['Reservation State',v.reservation_state],['Campaign Period',`${v.campaign_starts_at} to ${v.campaign_ends_at}`],['Advertising Account Time Zone',v.time_zone],['Observed At',v.observed_at],['Valid Until',v.expires_at]];
   $('summary').replaceChildren(...rows.flatMap(([label,value])=>[node('dt',label),node('dd',value)]));$('reasons').replaceChildren(...v.reasons.map(r=>node('li',reasons[r])));
  }catch(error){if(ticket!==epoch||initial!==key())return;reset();if([409,503].includes(error.status)){$('notice').textContent='A current Google total-budget observation is unavailable for this saved run. No spending permission or reservation changed.';return;}throw error;}
 });
 monitor(current);return {reset,enable};
}
