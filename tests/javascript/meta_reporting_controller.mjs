const mode='__MODE__',$=id=>document.getElementById('report-'+id),assert=(v,m)=>{if(!v)throw Error(m);},nativeFetch=window.fetch;
let cookies='__Host-inlet_csrf='+'a'.repeat(43),release=null,lose=true,selected=false;
Object.defineProperty(document,'cookie',{configurable:true,get:()=>cookies});
const calls=[],basis='b'.repeat(64),sid='c'.repeat(32),digest='d'.repeat(64);
const wait=async(fn,msg)=>{const end=Date.now()+5000;while(Date.now()<end){if(fn())return;await new Promise(r=>setTimeout(r,10));}throw Error(msg+' '+$('message').textContent);};
const change=(name,value)=>{$(name).value=value;$(name).dispatchEvent(new Event('change'));};
window.fetch=async(url,init={})=>{
 const path=String(url),body=init.body?JSON.parse(init.body):null;calls.push({path,body});let value;
 if(path.endsWith('/session'))value={user_id:'alice'};
 else if(path.endsWith('/workspaces'))value=[{id:1,name:'One'},{id:2,name:'Two'}];
 else if(path.endsWith('/planning/accounts'))value={complete:true,accounts:[{id:2,name:'Meta One',platform:'meta_ads'},{id:3,name:'Meta Two',platform:'meta_ads'}]};
 else if(path.includes('/event-selection?'))value={account_id:Number(new URL(path,location.origin).searchParams.get('account_id')),state:selected?'selected':'none',selection_id:selected?sid:null,selection_digest:selected?digest:null,label:'Website Purchases — Count Only',metric_family:'actions'};
 else if(path.endsWith('/available-range'))value={...body,basis_digest:basis,completion_id:'e'.repeat(32),state:'available',time_zone:'UTC',spending_authorized:false};
 else if(path.endsWith('/event-options')){assert(body.basis_digest===basis&&body.starts_on==='2026-08-01','reviewed dates carried');value={account_id:2,basis_digest:basis,options:[{option_id:basis,label:'Website Purchases — Count Only',metric_family:'actions',native_event:'offsite_conversion.fb_pixel_purchase'}]};}
 else if(path.endsWith('/event-selection')){selected=true;value={account_id:2,state:'selected',selection_id:sid,selection_digest:digest,label:'Website Purchases — Count Only',metric_family:'actions'};}
 else if(path.endsWith('/capture-intents')){if(mode==='prepare_replay'&&lose){lose=false;throw TypeError('fixture lost preparation');}value={...body,request_id:'f'.repeat(32)};}
 else if(path.endsWith('/captures')){
  assert(body.basis_digest===basis&&body.starts_on==='2026-08-01','capture basis retained');
  if(mode==='replay'&&lose){lose=false;throw TypeError('fixture lost response');}
  if(!['replay','prepare_replay'].includes(mode))await new Promise(resolve=>{release=resolve;});
  value={account_id:2,capture_id:body.request_id,selection_id:sid,selection_digest:digest,starts_on:body.starts_on,ends_on:body.ends_on,returned_rows:3,present_count_rows:2,explicit_zero_rows:1,missing_count_rows:1,profile:'meta.website-purchase-count.campaign-day.v1',monetary_value:'unsupported',effective_attribution:'unknown',omitted_days:'not_zero',spending_authorized:false};
 }else throw Error('unexpected '+path);
 return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
};
try{
 await import('/app/assets/reporting.mjs');await wait(()=>!$('controls').hidden,'loaded');change('workspace','1');await wait(()=>$('account').options.length===3,'accounts');change('account','2');await wait(()=>!$('range').disabled,'state');assert(!$('meta-scope').hidden&&$('range').textContent==='Review Available Range','honest count-only mode');
 $('start').value='2026-08-01';$('end').value='2026-09-30';$('form').requestSubmit();await wait(()=>!$('discover').disabled,'range reviewed');assert($('message').textContent.includes('No Fresh Aggregate Read'),'no fresh import claim');$('discover').click();await wait(()=>!$('events').hidden,'options');assert($('option').value==='','no automatic choice');change('option',basis);$('confirm').click();$('confirm').click();await wait(()=>!$('capture').hidden&&!$('capture').disabled,'confirmation');assert(calls.filter(c=>c.path.endsWith('/event-selection')).length===1,'one explicit confirmation');
 $('capture').click();$('capture').click();
 if(['replay','prepare_replay'].includes(mode)){
  await wait(()=>!$('retry').disabled,'unknown outcome');assert($('capture-result').hidden,'no optimistic receipt');$('retry').click();await wait(()=>!$('capture-result').hidden,'retained retry');const posts=calls.filter(c=>c.path.endsWith(mode==='replay'?'/captures':'/capture-intents'));assert(posts.length===2&&JSON.stringify(posts[0].body)===JSON.stringify(posts[1].body),'same exact retry intent');assert($('capture-details').textContent.includes('Rows With Explicit Zero1')&&$('capture-details').textContent.includes('Returned Rows Missing A Count1')&&$('capture-details').textContent.includes('Missing, Not Zero')&&$('capture-details').textContent.includes('Money / ROASUnavailable'),'separate presence and money states');assert(!$('use-capture').disabled,'existing explicit Planning handoff available');
 }else{
  await wait(()=>release!==null,'capture in flight');if(mode==='account')change('account','3');else if(mode==='workspace')change('workspace','2');else{cookies='__Host-inlet_csrf='+'z'.repeat(43);window.dispatchEvent(new Event('focus'));}
  release();await new Promise(r=>setTimeout(r,80));assert($('capture-result').hidden&&$('range-result').hidden&&$('pending').hidden,'late response cannot restore old scope');assert(calls.filter(c=>c.path.endsWith('/captures')).length===1,'no automatic repeat');if(mode==='session')assert($('controls').hidden,'session clears all');
 }
 await nativeFetch('/result',{method:'POST',body:'PASS'});
}catch(error){await nativeFetch('/result',{method:'POST',body:error.stack||String(error)});}finally{window.fetch=nativeFetch;}
