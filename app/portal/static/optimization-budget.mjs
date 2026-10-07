// Intent-only browser boundary. No provider identifiers, qualification or limits
// beyond the customer's total and named aggressiveness are submitted here.
const id=v=>typeof v==='string'&&/^[a-f0-9]{32}$/.test(v);
const digest=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const integer=v=>Number.isSafeInteger(v)&&v>=0&&v<=1000000000000000;
const aggression=v=>['conservative','balanced','assertive'].includes(v);
const sameSelection=(a,b)=>['goal_id','goal_revision','account_id','option_id'].every(k=>a?.[k]===b?.[k]);
export function mandateRequest(selection,total,aggressiveness,previous=null){
 if(!id(selection?.goal_id)||!Number.isSafeInteger(selection.goal_revision)||selection.goal_revision<1||!Number.isSafeInteger(selection.account_id)||selection.account_id<1||!digest(selection.option_id))throw new Error('Choose a current goal, account and named target.');
 if(!integer(total)||total%10000)throw new Error('Enter a USD amount with at most two decimal places.');
 if(!aggression(aggressiveness))throw new Error('Choose aggressiveness.');
 if(previous&&(!id(previous.id)||!Number.isSafeInteger(previous.revision)||previous.revision<1))throw new Error('Refresh the saved mandate before editing.');
 return {intent:{selection:{goal_id:selection.goal_id,goal_revision:selection.goal_revision,account_id:selection.account_id,option_id:selection.option_id},total_cap_micros:total,aggressiveness},...(previous?{mandate_id:previous.id,expected_revision:previous.revision}:{})};
}
export function checkedPrepared(value,intent,previous=null){
 const valid=value?.schema_version==='inlet.prepared-optimization-mandate.v1'&&['draft','active'].includes(value.state)&&value.dispatch_qualified===false&&value.currency==='USD'&&id(value.mandate_id)&&Number.isSafeInteger(value.revision)&&value.revision>0&&digest(value.policy_digest)&&digest(value.preparation_digest)&&sameSelection(value.selection,intent.selection)&&value.total_cap_micros===intent.total_cap_micros&&value.aggressiveness===intent.aggressiveness&&['total_cap_micros','per_plan_cap_micros','positive_change_cap_micros'].every(k=>integer(value[k]))&&value.positive_change_cap_micros<=value.per_plan_cap_micros&&value.per_plan_cap_micros<=value.total_cap_micros&&['contract_test','live'].includes(value.environment)&&typeof value.target_label==='string'&&value.target_label.length>0&&value.target_label.length<=160&&Number.isSafeInteger(value.affected_target_count)&&value.affected_target_count>0&&value.affected_target_count<=200&&typeof value.time_zone==='string'&&value.time_zone.length>0&&Number.isFinite(Date.parse(value.starts_at))&&Date.parse(value.starts_at)<Date.parse(value.ends_at);
 if(!valid||(previous&&['mandate_id','revision','policy_digest','preparation_digest'].some(k=>value[k]!==previous[k])))throw new Error('The exact spending mandate could not be verified. Refresh owned status.');
 return value;
}
export function consentRequest(prepared,selection){
 if(!sameSelection(prepared?.selection,selection))throw new Error('Review the current target and spending mandate again.');
 return {selection:{...prepared.selection},expected_revision:prepared.revision,policy_digest:prepared.policy_digest,preparation_digest:prepared.preparation_digest};
}
