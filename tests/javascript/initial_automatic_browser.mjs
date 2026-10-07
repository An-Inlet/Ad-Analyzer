// Actual customer page, APIs, configured worker and MockHTTP provider; no fetch stubs.
const $=id=>document.getElementById('ip-'+id),assert=(ok,msg)=>{if(!ok)throw Error(msg);};
const until=async(fn,message)=>{const end=Date.now()+20000;while(!await fn()){if(Date.now()>end)throw Error(message+' · '+$('status').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(id,value,type='change')=>{$(id).value=value;$(id).dispatchEvent(new Event(type));};
const settled=()=>!$('refresh').disabled;
try{
await import('/app/assets/initial-planning.mjs');
await until(()=>settled()&&$('workspace').options.length===2,'workspace');change('workspace',$('workspace').options[1].value);
await until(()=>settled()&&$('campaign').options.length===2,'owned campaign');change('campaign',$('campaign').options[1].value);change('goal',$('goal').options[1].value,'input');change('cpa','10','input');
$('capture').click();await until(()=>settled()&&!$('report').hidden,'actual captured report');$('confirm').checked=true;$('confirm').dispatchEvent(new Event('change'));$('calibrate').click();await until(()=>settled()&&!$('calibration').hidden,'actual calibration');
$('native').click();await until(()=>settled()&&$('target').options.length===2,'owned native GET');change('target',$('target').options[1].value);change('mandate','__PLANNING_MANDATE__');$('preview').click();await until(()=>settled()&&!$('result').hidden,'actual native preview');
assert($('automatic-start').disabled&&!$('automatic-confirm').checked,'no implicit initial Start');
$('automatic-options').click();await until(()=>settled()&&$('automatic-choice').options.length===2,'named initial rule and separate execution consent');change('automatic-choice','0');
assert($('automatic-summary').textContent.includes('Unsettled Reported Data'),'honest operational basis');assert($('automatic-summary').textContent.includes('Total Spending Limit'),'mandate remains bounded');assert($('automatic-start').disabled,'explicit consent required');
$('automatic-confirm').checked=true;$('automatic-confirm').dispatchEvent(new Event('change'));$('automatic-start').click();
if(__LOST_START__){
await until(()=>settled()&&$('status').textContent.includes('not available'),'lost response after committed Start');
assert($('automatic-start').disabled&&!$('automatic-confirm').checked,'uncertain response clears authority');
$('automatic-history').click();await until(()=>settled()&&$('automatic-runs').options.length===2,'recover actual original run');change('automatic-runs',$('automatic-runs').options[1].value);
}else await until(()=>settled()&&$('automatic-status').textContent.startsWith('running:'),'actual original Start');
assert(!$('automatic-confirm').checked,'confirmation cleared after Start');
const response=await fetch('/__fixture__/worker',{method:'POST'}),work=await response.json();assert(response.ok&&work.result==='completed','configured worker completed original initial decision');
$('automatic-read').click();await until(()=>settled()&&$('automatic-status').textContent.startsWith('waiting:'),'read original run');
$('automatic-stop').click();await until(()=>settled()&&$('automatic-status').textContent.startsWith('stopped:'),'explicit Stop');
$('automatic-history').click();await until(()=>settled()&&$('automatic-runs').options.length===2,'owned recovery history');assert($('automatic-start').disabled,'read history grants no Start');
$('logout').click();await until(()=>$('status').textContent==='Signed out.','logout');assert($('automatic').hidden&&!$('automatic-confirm').checked,'logout clears pending authority');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
