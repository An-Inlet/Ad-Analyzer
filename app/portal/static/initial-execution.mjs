// Explicit versioned review handoff. No authority, amount or native ID is sent.
const id=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const fail=()=>{throw Error('The execution review options could not be verified. Refresh current information.');};
export const unavailableText=reason=>({
  execution_runtime_unavailable:'Exact execution review is unavailable for this workspace.',
  separate_execution_consent_required:'A separately consented execution spending plan is required. Review its exact limits in Existing Campaigns.',
  matching_execution_mandate_unavailable:'No existing execution spending plan matches this preview. Review current scope and limits in Existing Campaigns.',
})[reason]||'Exact execution review is unavailable.';
export function executionOptions(value,preview){
  if(value?.schema_version!=='inlet.initial-preview-execution-options.v1'||!id(preview?.id)||value.preview_id!==preview.id||!digest(value.preview_digest)||value.financial_qualification!=='not_checked'||value.spending_authority!=='none'||!Array.isArray(value.options)||value.options.length>50||typeof value.truncated!=='boolean'||!['available','unavailable'].includes(value.status))fail();
  const unavailable=['execution_runtime_unavailable','separate_execution_consent_required','matching_execution_mandate_unavailable'];
  if((value.status==='available')!==Boolean(value.options.length)||(value.status==='available'?value.unavailable_reason!==null:!unavailable.includes(value.unavailable_reason)))fail();
  const seen=new Set();
  for(const option of value.options){
    if(!id(option.mandate_id)||!Number.isSafeInteger(option.mandate_revision)||option.mandate_revision<1||!digest(option.policy_digest)||option.currency!=='USD'||!['account_label','target_label'].every(k=>typeof option[k]==='string'&&option[k].length>0&&option[k].length<=160)||typeof option.time_zone!=='string'||option.time_zone.length>64)fail();
    try{new Intl.DateTimeFormat('en-US',{timeZone:option.time_zone});}catch{fail();}
    if(![option.starts_at,option.ends_at].every(v=>typeof v==='string'&&/(Z|[+-]\d\d:\d\d)$/.test(v)&&Number.isFinite(Date.parse(v)))||Date.parse(option.starts_at)>=Date.parse(option.ends_at))fail();
    const amounts=[option.total_cap_micros,option.per_plan_cap_micros,option.positive_change_cap_micros];
    if(!amounts.every(v=>Number.isSafeInteger(v)&&v>=0&&v<=1e15&&v%10000===0)||amounts[1]>amounts[0]||amounts[2]>amounts[0])fail();
    const key=option.mandate_id+':'+option.mandate_revision;if(seen.has(key))fail();seen.add(key);
  }
  // Snapshot response objects; later external mutations cannot change selected limits.
  return structuredClone(value);
}
export function executionIntent(options,index){
  if(!/^(0|[1-9]\d*)$/.test(String(index)))fail();
  const option=options?.options?.[Number(index)];
  if(!option||options.status!=='available')fail();
  return {expected_preview_digest:options.preview_digest,mandate_id:option.mandate_id,mandate_revision:option.mandate_revision};
}
export function checkExecutionPrepared(value,preview,intent,option){
  if(value?.schema_version!=='inlet.initial-preview-execution-prepared.v1'||value.preview_id!==preview.id||value.preview_digest!==intent.expected_preview_digest||!id(value.review_id)||!digest(value.review_digest)||!digest(value.plan_digest)||value.status!=='review_required'||value.spending_authority!=='none'||value.execution_mandate?.mandate_id!==intent.mandate_id||value.execution_mandate?.revision!==intent.mandate_revision||value.execution_mandate?.policy_digest!==option.policy_digest)fail();
  return value;
}
export function periodText(option){
  const format=new Intl.DateTimeFormat('en-GB',{timeZone:option.time_zone,year:'numeric',month:'short',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  return `${format.format(new Date(option.starts_at))} to ${format.format(new Date(option.ends_at))} (end excluded) · ${option.time_zone}`;
}
