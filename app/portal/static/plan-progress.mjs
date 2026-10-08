// Read-only display of separately observed sales; never a plan-effect assessment.
const same=(a,b)=>{
  if(a===b)return true;
  if(!a||!b||typeof a!=='object'||typeof b!=='object')return false;
  const keys=Object.keys(a).sort(),other=Object.keys(b).sort();
  return keys.length===other.length&&keys.every((key,i)=>key===other[i]&&same(a[key],b[key]));
};
const integer=value=>Number.isSafeInteger(value);
const stamp=value=>typeof value==='string'&&/T.*(?:Z|[+-]\d\d:\d\d)$/.test(value)&&Number.isFinite(Date.parse(value));
// Display bound, not a per-row bigint bound: 512 digits exceeds even all possible
// 64-character Unicode entry keys multiplied by the signed-bigint row magnitude.
const exact=value=>typeof value==='string'&&value.length<=513&&/^(?:0|-?[1-9][0-9]*)$/.test(value)&&value.replace(/^-/,'').length<=512;
const amount=(value,currency)=>{const n=BigInt(value),absolute=n<0n?-n:n;return `${currency} ${n<0n?'-':''}${absolute/1000000n}.${String(absolute%1000000n).padStart(6,'0')}`;};
const reasons=new Set(['goal_not_confirmed','goal_definition_unavailable','source_unavailable','measurement_basis_changed','ambiguous_local_boundary','no_closed_days','outside_retention','missing_history','incomplete_window','stale_source','import_in_progress','source_error','unreconciled_source','privacy_suppressed_source']);
export function clearPlanSalesProgress(host){host.replaceChildren();host.hidden=true;}
export function renderPlanSalesProgress(host,response,expected){
  clearPlanSalesProgress(host);
  const fail=()=>{throw Error('Sales progress did not match the displayed plan and confirmed goal.');};
  const goal=expected?.goal,definition=goal?.definition,window=definition?.target_window;
  if(!response||response.schema_version!=='inlet.plan-sales-progress.v1'||response.advertising_writes_enabled!==false||response.spending_authority!=='none'||response.manual_application!=='not_assessed'||response.attribution!=='unavailable'||response.workspace_id!==expected.workspaceId||response.plan_id!==expected.planId||response.version!==expected.version||response.document_digest!==expected.documentDigest||!same(response.goal,goal)||!stamp(response.as_of)||!definition||!integer(definition.target_micros)||definition.target_micros<=0||definition.target_micros>1e15||!window||!/^[A-Z]{3}$/.test(window.currency))fail();
  const sales=response.sales;
  if(response.binding_status==='unavailable'){
    if(!['goal_changed','goal_unavailable'].includes(response.binding_reason)||sales!==null||response.net_sales_micros_exact!==null)fail();
  }else if(response.binding_status==='matched'){
    if(response.binding_reason!==null||!sales||sales.schema_version!=='inlet.goal-sales-progress.v1'||sales.workspace_id!==expected.workspaceId||sales.goal_id!==goal.goal_id||sales.revision!==goal.revision||sales.metric!==definition.metric||sales.goal_achievement!=='not_assessed'||sales.attribution!=='unavailable'||sales.spending_authorized!==false||sales.as_of!==response.as_of||!['available_as_of','not_started','unavailable'].includes(sales.status)||!Array.isArray(sales.reasons)||sales.reasons.length>14||new Set(sales.reasons).size!==sales.reasons.length||sales.reasons.some(reason=>!reasons.has(reason)))fail();
    if(!same(sales.target_window,window)||sales.target_micros!==definition.target_micros||sales.store_id!==definition.store_id||sales.currency!==window.currency||sales.time_zone!==window.time_zone||! /^[a-f0-9]{64}$/.test(sales.definition_digest))fail();
    if(sales.status==='available_as_of'){
      const coverage=sales.coverage;
      if(!exact(response.net_sales_micros_exact)||typeof sales.net_sales_micros!=='number'||Number.isNaN(sales.net_sales_micros)||(Number.isFinite(sales.net_sales_micros)&&!Number.isInteger(sales.net_sales_micros))||(integer(sales.net_sales_micros)&&BigInt(sales.net_sales_micros)!==BigInt(response.net_sales_micros_exact))||sales.reasons.length||sales.import_in_progress!==false||!integer(sales.source_revision)||sales.source_revision<0||!stamp(sales.source_watermark)||!coverage||!integer(coverage.closed_day_count)||coverage.closed_day_count<1||coverage.closed_day_count>400||coverage.starts_on!==window.start||coverage.ends_on_exclusive>window.end||!['partial_period','full_window_as_of'].includes(coverage.extent)||((coverage.ends_on_exclusive===window.end)!==(coverage.extent==='full_window_as_of'))||!stamp(coverage.starts_at)||!stamp(coverage.ends_at_exclusive)||Date.parse(coverage.starts_at)>=Date.parse(coverage.ends_at_exclusive)||Date.parse(coverage.ends_at_exclusive)>Date.parse(sales.source_watermark)||Date.parse(sales.source_watermark)>Date.parse(sales.as_of)||(Date.parse(coverage.ends_on_exclusive)-Date.parse(coverage.starts_on))/86400000!==coverage.closed_day_count)fail();
    }else if(sales.net_sales_micros!==null||response.net_sales_micros_exact!==null||!sales.reasons.length)fail();
  }else fail();
  const fragment=document.createDocumentFragment(),line=(tag,value)=>{const node=document.createElement(tag);node.textContent=value;fragment.append(node);};
  line('h2','Observed Sales Progress');
  line('p',`Saved Plan Version ${expected.version} · Goal Revision ${goal.revision}`);
  line('p',`Original Target: ${amount(String(definition.target_micros),window.currency)} merchandise net sales · ${window.start} to ${window.end} (exclusive) · ${window.time_zone}`);
  line('p',`Read As Of: ${response.as_of}`);
  if(response.binding_status==='unavailable')line('p',`Unavailable: ${response.binding_reason}. The original confirmed goal is preserved; no replacement sales amount is shown.`);
  else{
    line('p',`Sales Status: ${sales.status}`);
    if(sales.status==='available_as_of'){
      line('p',`Observed Shopify Merchandise Net Sales: ${amount(response.net_sales_micros_exact,sales.currency)}`);
      line('p',`Measured Closed-Day Prefix: ${sales.coverage.starts_on} to ${sales.coverage.ends_on_exclusive} (exclusive) · ${sales.coverage.closed_day_count} days · ${sales.coverage.extent} · ${sales.time_zone}`);
      line('p',`Source Watermark: ${sales.source_watermark}`);
    }else line('p',`Unavailable Reasons: ${sales.reasons.join(', ')}`);
  }
  line('p','This is a current sales observation for the saved goal, not evidence of this plan’s impact or goal achievement. Manual application is not assessed; attribution is unavailable. Refunds and corrections can change later readings. No advertising writes or spending authority.');
  host.replaceChildren(fragment);host.hidden=false;
}
