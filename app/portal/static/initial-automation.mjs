// Initial automatic Start is an explicit exact-preview commitment, never human approval.
const id=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const amount=value=>Number.isSafeInteger(value)&&value>0&&value<=1e15;
const fail=()=>{throw Error('The initial automation choices could not be verified. Read current choices again.');};
export function initialOptions(value,preview){
  if(preview?.schema_version!=='inlet.initial-efficiency-preview.v2'||!id(preview.id)||value?.schema_version!=='inlet.initial-rule-automatic-options.v1'||value.preview_id!==preview.id||!digest(value.preview_digest)||value.spending_authority!=='none'||value.correction_status!=='as_observed_unsettled'||value.causal_lift!=='unavailable'||value.financial_qualification!=='checked_separately_before_each_change'||typeof value.truncated!=='boolean'||!Array.isArray(value.options)||value.options.length>20)fail();
  const seen=new Set();
  for(const option of value.options){
    const p=option.policy,m=option.mandate,key=`${p?.policy_id}/${p?.revision}/${m?.mandate_id}/${m?.revision}`;
    if(option.schema_version!=='inlet.initial-rule-automatic-option.v1'||option.decision_basis!=='initial_reported_efficiency_rule'||!id(p?.policy_id)||!Number.isSafeInteger(p.revision)||p.revision<1||!digest(option.policy_digest)||!id(m?.mandate_id)||!id(m.consent_id)||!id(m.ledger_id)||!digest(m.policy_digest)||!Number.isSafeInteger(m.revision)||m.revision<1||!['contract_test','live'].includes(m.environment)||option.currency!=='USD'||!amount(option.total_limit_micros)||!amount(option.maximum_adjustment_micros)||typeof option.label!=='string'||!option.label.length||option.label.length>100||typeof option.selected_rule!=='string'||!option.selected_rule.length||option.selected_rule.length>64||![option.lifetime_seconds,option.cadence_seconds].every(n=>Number.isSafeInteger(n)&&n>0&&n<=300)||seen.has(key))fail();
    seen.add(key);
  }
  return value;
}
export function initialStartIntent(choices,index){
  if(!choices||index===''||!/^\d+$/.test(index)||!choices.options[Number(index)])fail();
  const option=choices.options[Number(index)];
  return {schema_version:'inlet.start-initial-reported-rule-automation.v1',decision_basis:'initial_reported_efficiency_rule',preview_id:choices.preview_id,expected_preview_digest:choices.preview_digest,mandate:option.mandate,policy:option.policy,expected_policy_digest:option.policy_digest};
}
function checkedStatus(value,identifier=null){
  if(!id(value?.run_id)||(identifier!==null&&value.run_id!==identifier)||value.session_bound!==true||!['contract_test','live'].includes(value.environment)||!['unavailable','running','waiting','stopped','expired','blocked'].includes(value.status)||typeof value.reason!=='string'||typeof value.message!=='string'||value.message.length>300)throw Error('The original session run could not be verified. Read recent runs before continuing.');
  return value;
}
export function initialAutomation({$,api,guard,summary,money,say,state,invalidate}){
  let choices=null,selectedRun=null;
  const path=()=>`/workspaces/${encodeURIComponent(state().wid)}/execution/automation`;
  function clear(){choices=null;$('automatic-choice').replaceChildren(new Option('Choose…',''));$('automatic-confirm').checked=false;$('automatic-summary').replaceChildren();}
  function reset(){clear();selectedRun=null;$('automatic-runs').replaceChildren(new Option('Choose…',''));$('automatic-status').textContent='';}
  function enable(){const {busy,wid,preview}=state();$('automatic').hidden=!wid;$('automatic-options').disabled=busy||preview?.schema_version!=='inlet.initial-efficiency-preview.v2';$('automatic-choice').disabled=busy||!choices?.options.length;$('automatic-confirm').disabled=busy||!$('automatic-choice').value;$('automatic-start').disabled=busy||!choices||!$('automatic-choice').value||!$('automatic-confirm').checked;$('automatic-history').disabled=busy||!wid;$('automatic-runs').disabled=busy;$('automatic-read').disabled=busy||!selectedRun;$('automatic-stop').disabled=busy||!selectedRun;}
  function show(value){$('automatic-status').textContent=`${value.status}: ${value.message}`;}
  $('automatic-options').onclick=()=>guard(async turn=>{clear();const preview=state().preview;const value=initialOptions(await api(path()+'/initial-options/'+preview.id,turn),preview);if(state().preview!==preview)throw Error('The preview changed. Read current choices.');choices=value;$('automatic-choice').replaceChildren(new Option('Choose…',''),...value.options.map((o,i)=>new Option(`${o.label} · ${money(o.total_limit_micros,o.currency)} total limit`,String(i))));say(value.options.length?'Choose an initial rule and execution spending plan. Review the exact preview before Start.':'No initial automatic policy and matching execution spending plan are available.');});
  $('automatic-choice').onchange=()=>{invalidate();$('automatic-confirm').checked=false;$('automatic-summary').replaceChildren();const option=choices?.options[Number($('automatic-choice').value)];if($('automatic-choice').value!==''&&option){const p=state().preview;summary('automatic-summary',[['Basis','Initial Reported Efficiency Rule; Unsettled Reported Data'],['Rule',option.selected_rule],['Execution Environment',option.mandate.environment==='live'?'Live':'Offline Contract Test'],['Current Budget',money(p.before_budget_micros,option.currency)],['Proposed Budget',money(p.after_budget_micros,option.currency)],['Maximum Nominal Adjustment',money(option.maximum_adjustment_micros,option.currency)],['Total Spending Limit',money(option.total_limit_micros,option.currency)],['Maximum Session Duration',`${option.lifetime_seconds} seconds, bounded by preview and consent expiry`],['Check Cadence',`${option.cadence_seconds} seconds`],['Financial Qualification','Checked Separately Before Change'],['Causal Lift','Unavailable']]);}enable();};
  $('automatic-confirm').onchange=enable;
  $('automatic-start').onclick=()=>guard(async turn=>{if(!$('automatic-confirm').checked)throw Error('Review and confirm the exact initial preview and execution limits.');const intent=initialStartIntent(choices,$('automatic-choice').value);$('automatic-confirm').checked=false;selectedRun=null;$('automatic-runs').replaceChildren(new Option('Choose…',''));$('automatic-status').textContent='Start requested. If the response is unavailable, read recent runs before continuing.';const value=checkedStatus(await api(path()+'/start',turn,'POST',intent));selectedRun=value.run_id;$('automatic-runs').replaceChildren(new Option(`Original Run · ${value.status}`,value.run_id));$('automatic-runs').value=value.run_id;clear();show(value);say('Initial session run recorded. Read its status to monitor the original decision.');});
  $('automatic-history').onclick=()=>guard(async turn=>{const value=await api(path()+'/runs',turn);if(!Array.isArray(value?.runs)||value.runs.length>20)throw Error('Recent session runs could not be verified.');const runs=value.runs.map(v=>checkedStatus(v));selectedRun=null;$('automatic-runs').replaceChildren(new Option('Choose…',''),...runs.map(v=>new Option(`${v.run_id.slice(0,12)} · ${v.status}`,v.run_id)));$('automatic-status').textContent='Select the original session run to read or stop it. No Start was retried.';});
  $('automatic-runs').onchange=()=>{invalidate();selectedRun=$('automatic-runs').value||null;$('automatic-confirm').checked=false;enable();};
  $('automatic-read').onclick=()=>guard(async turn=>{const original=selectedRun;show(checkedStatus(await api(path()+'/'+original,turn),original));});
  $('automatic-stop').onclick=()=>guard(async turn=>{const original=selectedRun;const value=checkedStatus(await api(path()+'/'+original+'/stop',turn,'POST'),original);if(value.status!=='stopped')throw Error('Stop was not confirmed. Read the original session run.');show(value);});
  return {clear,reset,enable};
}
