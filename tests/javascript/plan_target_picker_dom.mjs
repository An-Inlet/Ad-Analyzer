import {renderPlanTargetPicker,clearPlanTargetPicker} from './plan-target-picker.mjs';
const catalogs=await (await fetch('/catalogs.json')).json();
const originalFetch=window.fetch;let requests=0;
window.fetch=()=>{requests++;throw new Error('component must not fetch');};
const host=document.querySelector('#host');
const assert=(value,message)=>{if(!value)throw new Error(message);};
const rejects=(fn,message)=>{let rejected=false;try{fn();}catch{rejected=true;}assert(rejected,message);};
const change=(select,value)=>{select.value=value;select.dispatchEvent(new Event('change'));};
const input=(field,value)=>{field.value=value;field.dispatchEvent(new Event('input'));};
try {
 for(const source of catalogs){
  const catalog=structuredClone(source), n=catalog.native_observation;
  const now=Date.parse(catalog.metadata_observation.observed_at);
  const options={workspaceId:n.workspace_id,account:{id:n.account_id,name:'Brand <img src=x>',platform:n.platform},period:{starts_at:n.reporting_starts_at,ends_at:n.reporting_ends_at},currency:'USD',totalCeilingMicros:1000001};
  catalog.targets[0].entity.name='<img src=x onerror="window.injected=true">';
  catalog.metadata_observation.entities[0].name=catalog.targets[0].entity.name;
  let changed=0;
  let handle=renderPlanTargetPicker(host,catalog,options,()=>changed++,now);
  assert(!host.querySelector('img')&&!window.injected,'literal names');
  assert(host.textContent.includes('hypotheses')&&host.textContent.includes('Coverage'),'honest scope');
  assert(JSON.stringify(handle.readIntent(now))==='{"exclusions":[],"fixed_allocations":[]}','default include');
  const choices=host.querySelectorAll('select'),amounts=host.querySelectorAll('input');
  change(choices[0],'fixed');input(amounts[0],'1.000001');
  let intent=handle.readIntent(now);
  assert(intent.fixed_allocations[0].amount_micros===1000001,'exact micros');
  assert(Object.keys(intent.fixed_allocations[0].target).sort().join(',')==='account_id,canonical_entity_key,selection_key','selector only');
  const originalKey=intent.fixed_allocations[0].target.selection_key;
  intent.fixed_allocations[0].target.selection_key='mutated';catalog.targets[0].selection_key='mutated';
  assert(handle.readIntent(now).fixed_allocations[0].target.selection_key===originalKey,'fresh selector copy');
  for(const bad of ['', '-1','+1','1e2','0x10','NaN','Infinity',' 1','1 ','1.0000001','1,2','01','1.','1000000000.000001']){
   input(amounts[0],bad);rejects(()=>handle.readIntent(now),'invalid amount '+bad);
  }
  input(amounts[0],'0.000001');assert(handle.readIntent(now).fixed_allocations[0].amount_micros===1,'one micro');
  change(choices[0],'exclude');intent=handle.readIntent(now);
  assert(intent.exclusions.length===1&&intent.fixed_allocations.length===0&&amounts[0].disabled,'exclusive choice');
  assert(changed>0&&requests===0,'local interaction');
  rejects(()=>handle.readIntent(Date.parse(handle.expiresAt)),'exact expiry');
  const savedSelect=choices[0];const count=changed;
  clearPlanTargetPicker(host);change(savedSelect,'fixed');
  assert(changed===count&&host.hidden&&!host.childNodes.length,'revoked detached callbacks');
  rejects(()=>handle.readIntent(now),'clear revokes');
  handle=renderPlanTargetPicker(host,source,options,()=>{},now);
  renderPlanTargetPicker(host,source,options,()=>{},now);
  rejects(()=>handle.readIntent(now),'rerender revokes');
  for(const bad of [null,{...source,spending_authority:'active'},{...source,native_observation:{...n,workspace_id:n.workspace_id+1}}]){
   const previous=renderPlanTargetPicker(host,source,options,()=>{},now);
   rejects(()=>renderPlanTargetPicker(host,bad,options,()=>{},now),'bad render');
   assert(host.hidden&&!host.childNodes.length,'bad render clears');rejects(()=>previous.readIntent(now),'bad render revokes');
  }
  rejects(()=>renderPlanTargetPicker(host,source,options,()=>{},Date.parse(source.expires_at)),'expired render');
  const zero=renderPlanTargetPicker(host,source,{...options,totalCeilingMicros:0},()=>{},now);
  change(host.querySelector('select'),'fixed');input(host.querySelector('input'),'0');
  assert(zero.readIntent(now).fixed_allocations[0].amount_micros===0,'explicit zero');
  input(host.querySelector('input'),'0.000001');rejects(()=>zero.readIntent(now),'zero ceiling');
 }
 // Synthetic catalog at the component's cardinality boundary, not provider evidence.
 const many=structuredClone(catalogs[0]),n=many.native_observation;
 const now=Date.parse(many.metadata_observation.observed_at);
 const options={workspaceId:n.workspace_id,account:{id:n.account_id,name:'Many',platform:n.platform},
  period:{starts_at:n.reporting_starts_at,ends_at:n.reporting_ends_at},currency:'USD',totalCeilingMicros:10};
 const base=many.targets.find(t=>t.entity.kind==='campaign');
 many.targets=Array.from({length:101},(_,i)=>{
  const t=structuredClone(base);t.canonical_entity_key=(i+1).toString(16).padStart(64,'0');
  t.selection_key=(i+1000).toString(16).padStart(64,'0');t.native_settings_key=null;
  t.entity.reference.entity_id=String(i+1);return t;
 });
 many.metadata_observation.entities=many.targets.map(t=>t.entity);
 for(const c of many.metadata_observation.coverage)c.count=c.kind==='campaign'?101:0;
 let handle=renderPlanTargetPicker(host,many,options,()=>{},now);
 let modes=host.querySelectorAll('[data-role="target-choice"]');
 let amounts=host.querySelectorAll('[data-role="target-amount"]');
 for(const mode of modes)change(mode,'exclude');
 rejects(()=>handle.readIntent(now),'101 exclusions');
 change(modes[100],'include');assert(handle.readIntent(now).exclusions.length===100,'100 exclusions');
 for(let i=0;i<modes.length;i++){change(modes[i],'fixed');input(amounts[i],'0');}
 rejects(()=>handle.readIntent(now),'101 allocations');
 change(modes[100],'include');assert(handle.readIntent(now).fixed_allocations.length===100,'100 fixed');
 input(amounts[0],'0.000006');input(amounts[1],'0.000005');
 rejects(()=>handle.readIntent(now),'aggregate ceiling');
 input(amounts[1],'0.000004');assert(handle.readIntent(now).fixed_allocations.length===100,'exact ceiling');
 const realNow=Date.now;Date.now=()=>Date.parse(handle.expiresAt);
 try{rejects(()=>handle.readIntent(),'actual default clock expiry');}finally{Date.now=realNow;}
 for(const ceiling of [-1,1.5,1000000000000001,NaN]){
  rejects(()=>renderPlanTargetPicker(host,many,{...options,totalCeilingMicros:ceiling},()=>{},now),
   'invalid confirmed ceiling');
  assert(host.hidden&&!host.childNodes.length,'invalid context clears');
 }
 for(const currency of ['usd',['USD'],null,'US'])
  rejects(()=>renderPlanTargetPicker(host,many,{...options,currency},()=>{},now),'invalid currency');
 assert(requests===0,'no network');
 document.querySelector('#result').textContent='PASS';
}catch(error){document.querySelector('#result').textContent='FAIL '+error.stack;}
await originalFetch('/result',{method:'POST',body:document.querySelector('#result').textContent});
