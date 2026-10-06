const $=id=>document.getElementById('ip-'+id),assert=(ok,msg)=>{if(!ok)throw Error(msg);};
const until=async(fn,message)=>{const end=Date.now()+15000;while(!await fn()){if(Date.now()>end)throw Error(message+' · '+$('status').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(id,value,type='change')=>{$(id).value=value;$(id).dispatchEvent(new Event(type));};
const settled=()=>!$('refresh').disabled;
try{
const login=await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'planning-browser:first'})});assert(login.ok,'actual sign in');
await import('/app/assets/initial-planning.mjs');await until(()=>settled()&&$('workspace').options.length===2,'workspace');
change('workspace','__WORKSPACE__');await until(()=>settled()&&$('campaign').options.length===2,'owned campaigns');change('campaign','__CAMPAIGN__');change('goal','__GOAL__','input');change('cpa','10','input');
$('capture').click();await until(()=>settled()&&!$('report').hidden,'actual capture');assert($('observation').textContent.includes('purchase'),'selected event');assert($('observation').textContent.includes('10.000001'),'actual report spend');
$('confirm').checked=true;$('confirm').dispatchEvent(new Event('change'));$('calibrate').click();await until(()=>settled()&&!$('calibration').hidden,'actual calibration');assert($('calibration-summary').textContent.includes('evaluated'),'actual chronological replay');assert($('parameters').textContent.includes('fixture_explicit'),'named server selected rule visible');
assert($('native').disabled,'no fake financial native runtime');$('preview').click();await until(()=>settled()&&!$('result').hidden,'actual preview');assert($('preview-summary').textContent.includes('increase'),'initial reported direction');assert($('preview-summary').textContent.includes('Unavailable'),'missing native amount never zero');assert($('preview-reasons').textContent.includes('remaining spending capacity'),'remaining capacity disclosure');assert($('result').textContent.includes('Review handoff is unavailable'),'no fabricated action approval');
change('cpa','12','input');assert($('result').hidden&&$('calibration').hidden&&!$('confirm').checked,'objective edit invalidates prior preview');
$('logout').click();await until(()=>settled()&&$('status').textContent==='Signed out.','logout');assert($('selection').hidden&&$('result').hidden&&!$('observation').textContent,'logout clears owned values');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
