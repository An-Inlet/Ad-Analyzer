// Real configured API calls; the fixture carries an actual API-created original session.
const $=id=>document.getElementById('ip-'+id),assert=(ok,msg)=>{if(!ok)throw Error(msg);};
const until=async(fn,message)=>{const end=Date.now()+25000;while(!await fn()){if(Date.now()>end)throw Error(message+' · '+$('status').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(id,value,type='change')=>{$(id).value=value;$(id).dispatchEvent(new Event(type));};
const settled=()=>!$('refresh').disabled;
const original=window.fetch.bind(window),posts=[];let options,prepared;
window.fetch=async(url,init)=>{const response=await original(url,init);if(String(url).endsWith('/execution-review-options'))options=await response.clone().json();if(init?.method==='POST'){posts.push({url:String(url),body:init.body?JSON.parse(init.body):null});if(String(url).endsWith('/execution-review'))prepared=await response.clone().json();}return response;};
try{
await import('/app/assets/initial-planning.mjs');await until(()=>settled()&&$('workspace').options.length===2,'workspace');change('workspace',$('workspace').options[1].value);await until(()=>settled()&&$('campaign').options.length===2,'owned campaign');
change('campaign',$('campaign').options[1].value);change('goal',$('goal').options[1].value,'input');change('cpa','10','input');$('capture').click();await until(()=>settled()&&!$('report').hidden,'capture');$('confirm').checked=true;$('confirm').dispatchEvent(new Event('change'));$('calibrate').click();await until(()=>settled()&&!$('calibration').hidden,'calibration');$('native').click();await until(()=>settled()&&$('target').options.length===2,'native read');change('target',$('target').options[1].value);assert($('mandate').options.length>=2,'actual separately saved planning consent');assert([...$('mandate').options].some(o=>o.value==='__PLANNING_MANDATE__'),'original planning consent offered');change('mandate','__PLANNING_MANDATE__');$('preview').click();await until(()=>settled()&&!$('result').hidden,'current v2 preview');assert(!$('execution').hidden&&$('review').disabled,'v2 explicit handoff controls, no implied approval');
$('execution-refresh').click();await until(()=>settled()&&options,'actual options GET');
assert(options.financial_qualification==='not_checked'&&options.spending_authority==='none','no qualification implied');
if(__UNAVAILABLE__){
assert(options.unavailable_reason==='separate_execution_consent_required','planning consent not promoted');assert($('review').disabled&&!$('execution-plan').value,'no executable selection');assert($('review-status').textContent.includes('separately consented')&&$('existing-campaigns').getAttribute('href').startsWith('/app/optimization?workspace='),'honest recovery link');
await original('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}else{
assert(options.options.length===1&&!$('execution-plan').value&&$('review').disabled,'explicit selection required');change('execution-plan','0');assert($('execution-summary').textContent.includes('USD 50')&&$('execution-summary').textContent.includes('end excluded')&&$('execution-summary').textContent.includes('Not Checked'),'exact money period and unqualified state');$('review').click();await until(()=>settled()&&!$('review-link').hidden,'actual exact handoff');const sent=posts.find(p=>p.url.endsWith('/execution-review'));assert(Object.keys(sent.body).sort().join(',')==='expected_preview_digest,mandate_id,mandate_revision','exact three-field intent');assert(prepared.status==='review_required'&&prepared.spending_authority==='none','review required, not approved');assert(!posts.some(p=>/\/consent$|\/approval$|\/runs$|\/advance$/.test(p.url)),'no consent or approval or execution from planning UI');
window.location.assign($('review-link').href);
}
}catch(error){await original('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
