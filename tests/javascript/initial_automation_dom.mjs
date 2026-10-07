// Unit-only DOM/fetch doubles. Real API/TLS acceptance is a separate suite.
import assert from 'node:assert/strict';
import fs from 'node:fs';
class Element{
  value='';textContent='';hidden=false;disabled=false;checked=false;children=[];
  replaceChildren(...children){this.children=children;this.value='';this.textContent=children.map(c=>c.textContent).join('');}
  append(...children){this.children.push(...children);}
  removeAttribute(name){delete this[name];}
}
const elements=new Map([...fs.readFileSync('app/portal/static/initial-planning.html','utf8').matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element()]));
globalThis.Option=class extends Element{constructor(text,value){super();this.textContent=text;this.value=value;}};
globalThis.document={cookie:'__Host-inlet_csrf='+'c'.repeat(43),getElementById:id=>elements.get(id),createElement:()=>new Element(),querySelectorAll:()=>[...elements.values()]};
const $=id=>elements.get('ip-'+id),pid='a'.repeat(32),gid='b'.repeat(32),mid='c'.repeat(32),rid='d'.repeat(32),hash='a'.repeat(64);
const calls=[];let version='v2',pending=null,holdOptions=false,session='owner';
const options={schema_version:'inlet.initial-preview-execution-options.v1',preview_id:pid,preview_digest:hash,options:[{mandate_id:mid,mandate_revision:1,policy_digest:hash,account_label:'Brand',target_label:'Campaign <img>',currency:'USD',time_zone:'UTC',starts_at:'2026-10-01T00:00:00Z',ends_at:'2026-11-01T00:00:00Z',total_cap_micros:100000000,per_plan_cap_micros:10000000,positive_change_cap_micros:1000000}],truncated:true,status:'available',unavailable_reason:null,financial_qualification:'not_checked',spending_authority:'none'};
let failStart=false;
const automaticOptions={schema_version:'inlet.initial-rule-automatic-options.v1',preview_id:pid,preview_digest:hash,spending_authority:'none',correction_status:'as_observed_unsettled',causal_lift:'unavailable',financial_qualification:'checked_separately_before_each_change',truncated:false,options:[{schema_version:'inlet.initial-rule-automatic-option.v1',policy:{policy_id:'1'.repeat(32),revision:1},policy_digest:hash,mandate:{mandate_id:mid,revision:1,consent_id:'2'.repeat(32),policy_digest:hash,ledger_id:'3'.repeat(32),environment:'contract_test'},label:'Configured rule',currency:'USD',total_limit_micros:50000000,selected_rule:'explicit_rule',maximum_adjustment_micros:1000000,lifetime_seconds:120,cadence_seconds:60,decision_basis:'initial_reported_efficiency_rule'}]};
globalThis.fetch=async(path,init)=>{
  calls.push({path,method:init.method,body:init.body&&JSON.parse(init.body)});
  let value;
  if(path.endsWith('/session'))value={user_id:session};
  else if(path.endsWith('/workspaces'))value=[{id:1,name:'Brand'}];
  else if(path.endsWith('/options'))value={configured:true,native_catalog_available:false,campaigns:[{account_id:1,campaign_id:2,account_name:'Brand',campaign_name:'Campaign',currency:'USD'}]};
  else if(path.endsWith('/goals'))value=[{id:gid,revision:1,assessment:'confirmed',definition:{target_window:{currency:'USD'}}}];
  else if(path.endsWith('/captures'))value={id:'e'.repeat(32),cohort:{selected_event:'purchase',currency:'USD'}};
  else if(path.endsWith('/calibrations'))value={id:'f'.repeat(32),spending_authorized:false,empirical_qualification:false,status:'evaluated',rules:[],reasons:[]};
  else if(path.endsWith('/previews'))value={id:pid,schema_version:'inlet.initial-efficiency-preview.'+version,spending_authorized:false,empirical_qualification:false,review_available:false,objective:{cohort:{currency:'USD'}},reasons:[]};
  else if(path.includes('/initial-options/')){if(holdOptions)await new Promise(resolve=>pending=resolve);value=automaticOptions;}
  else if(path.endsWith('/automation/start')){if(failStart)throw Error('uncertain response');value={run_id:rid,status:'running',reason:'ready',environment:'contract_test',session_bound:true,message:'Original session only.'};}
  else if(path.endsWith('/automation/runs'))value={runs:[{run_id:rid,status:'running',reason:'ready',environment:'contract_test',session_bound:true,message:'Original session only.'}]};
  else if(path.endsWith('/stop'))value={run_id:rid,status:'stopped',reason:'customer_stopped',environment:'contract_test',session_bound:true,message:'Original session only.'};
  else if(path.endsWith('/execution-review-options')){if(holdOptions)await new Promise(resolve=>pending=resolve);value=options;}
  else if(path.endsWith('/review-status'))value={preview_id:pid,preview_digest:hash,request_available:true,financial_qualification:'not_checked',spending_authority:'none'};
  else if(path.endsWith('/execution-review')||path.endsWith('/review'))value={schema_version:'inlet.initial-preview-execution-prepared.v1',preview_id:pid,preview_digest:hash,review_id:rid,review_digest:hash,plan_digest:hash,execution_mandate:{mandate_id:mid,revision:1,policy_digest:hash},status:'review_required',spending_authority:'none'};
  else throw Error('unexpected endpoint '+path);
  return {ok:true,status:200,json:async()=>value};
};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
await import('../../app/portal/static/initial-planning.mjs');await flush();
$('workspace').value='1';$('workspace').onchange();await flush();
async function preview(){
  $('campaign').value='2';$('campaign').onchange();$('goal').value=gid;$('goal').oninput();$('cpa').value='10';$('cpa').oninput();
  await $('capture').onclick();$('confirm').checked=true;$('confirm').onchange();await $('calibrate').onclick();await $('preview').onclick();
  assert.equal($('result').hidden,false);
}

await preview();
assert.equal($('automatic-start').disabled,true);
await $('automatic-options').onclick();
$('automatic-choice').value='0';$('automatic-choice').onchange();
assert.equal($('automatic-confirm').checked,false);
assert.equal($('automatic-start').disabled,true);
$('automatic-confirm').checked=true;$('automatic-confirm').onchange();
failStart=true;await $('automatic-start').onclick();
assert.equal(calls.filter(c=>c.path.endsWith('/automation/start')).length,1);
assert.equal($('automatic-confirm').checked,false);
assert.ok($('status').textContent.includes('Nothing was automatically retried'));
await $('automatic-history').onclick();
assert.equal(calls.filter(c=>c.path.endsWith('/automation/start')).length,1);
$('automatic-runs').value=rid;$('automatic-runs').onchange();await $('automatic-stop').onclick();
assert.ok($('automatic-status').textContent.includes('stopped'));
await preview();holdOptions=true;const stale=$('automatic-options').onclick();await flush();$('cpa').value='12';$('cpa').oninput();pending();await stale;
assert.equal($('automatic-choice').children.length,1);
await preview();holdOptions=false;await $('automatic-options').onclick();$('automatic-choice').value='0';$('automatic-choice').onchange();$('automatic-confirm').checked=true;$('automatic-confirm').onchange();
document.cookie='__Host-inlet_csrf='+'d'.repeat(43);await $('automatic-start').onclick();
assert.equal(calls.filter(c=>c.path.endsWith('/automation/start')).length,1,'rotated same-owner session cannot submit displayed old consent');
console.log('initial automatic UI stale session, no automatic retry, recovery and Stop passed');
