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
const calls=[];let version=process.argv[2]==='v1'?'v1':'v2',pending=null,holdOptions=false,session='owner';
const options={schema_version:'inlet.initial-preview-execution-options.v1',preview_id:pid,preview_digest:hash,options:[{mandate_id:mid,mandate_revision:1,policy_digest:hash,account_label:'Brand',target_label:'Campaign <img>',currency:'USD',time_zone:'UTC',starts_at:'2026-10-01T00:00:00Z',ends_at:'2026-11-01T00:00:00Z',total_cap_micros:100000000,per_plan_cap_micros:10000000,positive_change_cap_micros:1000000}],truncated:true,status:'available',unavailable_reason:null,financial_qualification:'not_checked',spending_authority:'none'};
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
if(version==='v1'){
  assert.equal($('execution').hidden,true);assert.equal($('review').disabled,false);await $('review').onclick();
  assert.deepEqual(calls.find(c=>c.path.endsWith('/review')).body,{expected_preview_digest:hash});
  assert.ok(!calls.some(c=>c.path.endsWith('/execution-review-options')));
}else{
  assert.equal($('execution').hidden,false);assert.equal($('review').disabled,true);
  await $('execution-refresh').onclick();assert.equal($('review').disabled,true);assert.equal($('execution-plan').value,'');assert.equal($('execution-truncated').hidden,false);
  $('execution-plan').value='0';$('execution-plan').onchange();assert.equal($('review').disabled,false);assert.match($('execution-summary').textContent,/Campaign <img>.*USD 100.*Not Checked/);
  await $('review').onclick();assert.deepEqual(calls.find(c=>c.path.endsWith('/execution-review')).body,{expected_preview_digest:hash,mandate_id:mid,mandate_revision:1});
  assert.equal($('review-link').hidden,false);assert.equal($('review').disabled,true);assert.ok(!calls.some(c=>/\/approve|\/start|\/advance|\/consent$/.test(c.path)));
  await preview();holdOptions=true;const request=$('execution-refresh').onclick();await flush();assert.ok(pending);
  $('goal').oninput();pending();await request;assert.equal($('result').hidden,true);assert.equal($('execution-plan').children.length,1);assert.equal($('review-link').hidden,true);
  holdOptions=false;await preview();holdOptions=true;const changedSession=$('execution-refresh').onclick();await flush();document.cookie='__Host-inlet_csrf='+'x'.repeat(43);pending();await changedSession;
  assert.equal($('selection').hidden,true);assert.equal($('result').hidden,true);assert.equal($('execution-plan').children.length,1);
}
