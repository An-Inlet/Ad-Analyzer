const $=id=>document.getElementById(id),assert=(ok,message)=>{if(!ok)throw Error(message);};
async function until(fn,message){const end=Date.now()+20000;while(!fn()){if(Date.now()>end)throw Error(message);await new Promise(r=>setTimeout(r,20));}}
const control=async(action)=>{const r=await fetch('/__fixture__/'+action,{method:'POST'});assert(r.ok,'fixture control');};
const select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change'));};
const available=()=>$('goal-progress-data').textContent.includes('Available As Of Import');
try{
  await import('/app/assets/portal.mjs');
  await until(()=>!$('application').hidden&&!$('retry').disabled,'session');
  select('workspace',$('workspace').options[1].value);
  await until(()=>!$('workspace-content').hidden&&!$('retry').disabled,'workspace');
  const goal=$('goal').options[1].value;select('goal',goal);
  await until(available,'real signed imported sales');
  assert($('goal-progress-data').textContent.replace(/\s/g,' ').includes('-USD 10.00'),'refund processing remains signed');
  for(const text of ['Partial Target Period','Closed Day Count','Source Watermark','As Of','Not Assessed','Spending PermissionNone'])assert($('goal-progress-data').textContent.includes(text),text);
  await control('importing');$('goal-progress-refresh').click();
  await until(()=>$('goal-progress-reasons').textContent.includes('still in progress'),'unavailable real source');
  assert($('goal-progress-data').textContent.includes('Imported Net SalesUnavailable')&&!$('goal-progress-data').textContent.includes('-USD'),'no retained numeric amount');
  await control('complete');$('goal-progress-refresh').click();await until(available,'refresh current import');
  $('goal-form').elements.namedItem('target').dispatchEvent(new Event('input',{bubbles:true}));
  assert($('goal-progress-data').textContent===''&&$('goal-progress-refresh').hidden,'unsaved edits clear progress');
  select('goal',goal);await until(available,'reload saved goal');
  await control('hold');$('goal-progress-refresh').click();
  await control('held');
  select('workspace','');await control('release');await new Promise(r=>setTimeout(r,100));
  assert($('goal-progress-data').textContent===''&&$('goal-progress').hidden,'late other-workspace result discarded');
  select('workspace',$('workspace').options[1].value);
  await until(()=>!$('workspace-content').hidden&&!$('retry').disabled,'workspace reload');select('goal',goal);await until(available,'saved goal reload');
  await control('hold');$('goal-progress-refresh').click();
  await control('held');
  $('logout').click();await until(()=>$('application').hidden&&!$('retry').disabled,'actual logout');
  await control('release');await new Promise(r=>setTimeout(r,100));
  assert($('goal-progress-data').textContent===''&&$('goal-progress').hidden,'late signed-out result discarded');
  await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
