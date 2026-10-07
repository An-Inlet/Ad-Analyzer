const $=id=>document.getElementById(id), assert=(ok,message)=>{if(!ok)throw new Error(message);};
const until=async(test,message)=>{const end=Date.now()+20000;while(!test()){if(Date.now()>end)throw new Error(message+' · '+$('execution-message').textContent);await new Promise(r=>setTimeout(r,20));}};
try{
await import('/app/assets/execution.mjs');
await until(()=>$('execution-run-state').textContent.includes('Ready')&&!$('execution-refresh').disabled,'linked saved run loaded');
assert($('execution-run-state').textContent.includes('Contract Test'),'no live claim');
async function approveStart(){ $('execution-review-check').checked=true;$('execution-review-check').dispatchEvent(new Event('change'));$('execution-approve').click();await until(()=>!$('execution-start').disabled,'approved');$('execution-start').click();await until(()=>$('execution-run-state').textContent.includes('Ready')&&!$('execution-refresh').disabled,'durable run');}
async function advanceTo(state){for(let i=0;i<30;i++){if($('execution-run-state').textContent.includes(state))return;$('execution-advance').click();await until(()=>!$('execution-refresh').disabled,'step completed');}throw new Error('did not reach '+state);}
if('__SCENARIO__'==='unknown'){
await fetch('/__fixture__/unknown',{method:'POST'});$('execution-advance').click();await until(()=>!$('execution-refresh').disabled&&$('execution-run-state').textContent.includes('Unknown'),'unknown original request');await fetch('/__fixture__/recover',{method:'POST'});assert($('execution-advance').disabled,'unknown cannot advance');[...$('execution-steps').querySelectorAll('button')].find(button=>button.textContent==='Check Original Request').click();await until(()=>!$('execution-refresh').disabled,'reconciliation without replay');assert($('execution-run-state').textContent.includes('Unknown'),'absent resource is not terminal no effect');
}else{
await advanceTo('Created Paused');assert(!$('execution-activate').disabled,'separate activation available');
if(['revoked','source','media','declaration','profile'].includes('__SCENARIO__')){
await fetch('__SCENARIO__'==='revoked'?'/__fixture__/revoke-next':'/__fixture__/invalidate',{method:'POST'});$('execution-activate').click();await until(()=>!$('execution-refresh').disabled,'revoked original session response');assert($('execution-review').hidden,'no activation review after original session revoke');
}else{
$('execution-activate').click();await until(()=>$('execution-review-title').textContent==='Separate Activation Review'&&!$('execution-refresh').disabled,'separate activation review');assert($('execution-start').disabled,'activation unapproved');await approveStart();
if('__SCENARIO__'==='unknown_activation'){
await fetch('/__fixture__/unknown',{method:'POST'});$('execution-advance').click();await until(()=>!$('execution-refresh').disabled&&$('execution-run-state').textContent.includes('Unknown'),'unknown activation');await fetch('/__fixture__/recover',{method:'POST'});assert($('execution-advance').disabled,'unknown activation cannot replay');[...$('execution-steps').querySelectorAll('button')].find(button=>button.textContent==='Check Original Request').click();await until(()=>!$('execution-refresh').disabled,'activation reconciliation');assert($('execution-run-state').textContent.includes('Unknown'),'old paused state does not prove no effect');
}else{await advanceTo('Activation Observed');assert($('execution-run-state').textContent.includes('Exposure Reservation Retained'),'retained parent hold');
const receiptButton=$('execution-steps').querySelector('button');receiptButton.click();await until(()=>$('execution-receipt').textContent.includes('Effective Time Unavailable'),'actual latest receipt');assert($('execution-receipt').textContent.includes('Verified Target State'),'state not causal effect');
$('execution-refresh').click();await until(()=>$('execution-run-state').textContent.includes('Activation Observed')&&!$('execution-refresh').disabled,'saved owned status');$('execution-revoke').click();await until(()=>$('execution-message').textContent.includes('Execution consent revoked.')&&!$('execution-refresh').disabled,'revoke consent');$('execution-logout').click();await until(()=>$('execution-message').textContent==='Signed out.','logout');assert($('execution-runs').hidden,'session cleared');
}}}
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
