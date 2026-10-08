// Real customer page and APIs; the harness supplies only an API-created session.
const $=id=>document.getElementById('ip-'+id),assert=(ok,msg)=>{if(!ok)throw Error(msg);};
const until=async(fn,message)=>{const end=Date.now()+25000;while(!await fn()){if(Date.now()>end)throw Error(message+' · '+$('status').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(id,value,type='change')=>{$(id).value=value;$(id).dispatchEvent(new Event(type));};
const settled=()=>!$('refresh').disabled;
const realFetch=globalThis.fetch.bind(globalThis),requests=[];
globalThis.fetch=(url,init)=>{requests.push({url:String(url),method:init?.method||'GET'});return realFetch(url,init);};
try{
await import('/app/assets/initial-planning.mjs');
await until(()=>settled()&&$('workspace').options.length===2,'workspace');
change('workspace',$('workspace').options[1].value);
await until(()=>settled()&&$('campaign').options.length===2,'owned campaign');
change('campaign',$('campaign').options[1].value);change('goal',$('goal').options[1].value,'input');change('cpa','10','input');
$('capture').click();await until(()=>settled()&&!$('report').hidden,'actual capture');
$('confirm').checked=true;$('confirm').dispatchEvent(new Event('change'));$('calibrate').click();
await until(()=>settled()&&!$('calibration').hidden,'actual calibration');
$('native').click();await until(()=>settled()&&$('target').options.length===2,'real native GET');
assert($('mandate').options.length===1,'no pre-seeded consent');
change('target',$('target').options[1].value);assert(!$('budget').hidden,'budget form');
assert($('budget-goal').textContent.includes('end excluded'),'exact confirmed goal period');
if(__UNAVAILABLE__){
$('budget-prepare').click();await until(()=>settled()&&$('status').textContent.includes('Spending-limit review is unavailable'),'unavailable configured policy');
assert($('budget-review').hidden&&!$('mandate').value,'no manufactured consent');
}else{
const original=globalThis.fetch.bind(globalThis);let prepared,consented;
globalThis.fetch=async(url,init)=>{const response=await original(url,init);if(init?.method==='POST'&&String(url).endsWith('/budget-mandates')){const body=JSON.parse(init.body);assert(Object.keys(body.intent).sort().join(',')==='aggressiveness,selection,total_cap_micros','customer intent only');prepared=await response.clone().json();}if(init?.method==='POST'&&String(url).endsWith('/consent'))consented=await response.clone().json();return response;};
$('budget-prepare').click();await until(()=>settled()&&!$('budget-review').hidden,'exact derived cap review');
assert(prepared.state==='draft'&&prepared.execution_available===false,'draft is not activation');
assert($('budget-consent').disabled,'explicit checkbox required');
$('budget-confirm').checked=true;$('budget-confirm').dispatchEvent(new Event('change'));$('budget-consent').click();
await until(()=>settled()&&!!$('mandate').value,'exact consent');assert(consented.state==='active'&&!consented.exposure_qualified,'conditional consent only');
assert($('mandate').value===prepared.mandate_id,'server returned identity, no pasted ID');
$('preview').click();await until(()=>settled()&&!$('result').hidden,'actual native v2 preview');
assert(!$('preview-summary').textContent.includes('Unavailable'),'native amount present');
assert(!$('review')&&!$('automatic-start')&&!$('execution-refresh'),'planning page has no execution controls');
// Editing the amount clears active selection as well as the draft and result.
change('budget-total',$('budget-total').value,'input');assert(!$('mandate').value&&$('budget-review').hidden&&$('result').hidden,'changed intent clears active selection');
// No old response may restore authority after a workspace change.
let entered=false,release;globalThis.fetch=async(url,init)=>{const response=await original(url,init);if(init?.method==='POST'&&String(url).endsWith('/budget-mandates')){entered=true;await new Promise(r=>{release=r;});}return response;};
$('budget-prepare').click();await until(()=>entered,'hold actual prepare response');change('workspace','');release();await new Promise(r=>setTimeout(r,100));
assert($('budget').hidden&&$('budget-review').hidden&&!$('mandate').value,'late prepare discarded');globalThis.fetch=original;
$('logout').click();await until(()=>settled()&&$('status').textContent==='Signed out.','logout');
}
assert(!requests.some(r=>r.url.includes('/execution/')||r.url.endsWith('/review')),'no execution or advertising approval requests');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
