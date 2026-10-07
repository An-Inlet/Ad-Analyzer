const $=id=>document.getElementById(id),assert=(ok,m)=>{if(!ok)throw Error(m);};
const until=async(test,message)=>{const end=Date.now()+20000;while(!test()){if(Date.now()>end)throw Error(message+' '+$('execution-message').textContent+' '+$('envelope-notice').textContent);await new Promise(r=>setTimeout(r,20));}};
try{
assert((await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'configured-google:browser'})})).ok,'actual login');
history.replaceState(null,'','/app/execution/__WID__/__RUN__');await import('/app/assets/execution.mjs');
await until(()=>!$('envelope-read').disabled,'saved owned run');assert($('envelope-result').hidden,'no automatic native read');
$('envelope-read').click();await until(()=>!$('execution-refresh').disabled&&!$('envelope-result').hidden,'actual observation');
assert($('envelope-notice').textContent.includes('Match'),'native original matched');
assert($('envelope-summary').textContent.includes('Original Native Campaign TotalUSD 0.00003'),'original native amount');
assert($('envelope-summary').textContent.includes('Recorded Reservation — Separate Allocation'),'reservation distinct');
assert($('envelope-reasons').textContent.includes('do not establish a financial spending bound'),'no qualification');
assert(!$('envelope-summary').textContent.includes('customers/'),'no native ids');
await fetch('/__fixture__/lower',{method:'POST'});$('envelope-read').click();await until(()=>!$('execution-refresh').disabled&&$('envelope-notice').textContent.includes('Changed'),'actual native drift');
assert($('envelope-summary').textContent.includes('Observed Native Campaign TotalUSD 0.00002'),'observed lower amount');
await fetch('/__fixture__/disable',{method:'POST'});$('envelope-read').click();await until(()=>!$('execution-refresh').disabled&&$('envelope-notice').textContent.includes('unavailable'),'disabled read');assert($('envelope-result').hidden,'old data cleared');
$('execution-logout').click();await until(()=>$('execution-message').textContent==='Signed out.','logout');assert($('envelope-result').hidden&&$('envelope-section').hidden,'session cleared');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
