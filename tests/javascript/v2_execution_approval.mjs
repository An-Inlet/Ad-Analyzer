const $=id=>document.getElementById('opt-'+id),assert=(ok,msg)=>{if(!ok)throw Error(msg);};
const until=async(fn,message)=>{const end=Date.now()+15000;while(!await fn()){if(Date.now()>end)throw Error(message+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
try{
await import('/app/assets/optimization.mjs');await until(()=>!$('refresh').disabled&&!$('review').hidden,'ordinary owned exact review');
assert($('review-summary').textContent.includes('USD'),'exact owned money displayed');assert($('approve').disabled&&$('admit').disabled&&!$('review-check').checked,'separate explicit approval remains required');$('review-check').checked=true;$('review-check').dispatchEvent(new Event('change'));$('approve').click();await until(()=>!$('refresh').disabled&&$('message').textContent.includes('Exact plan approved'),'ordinary explicit approval');assert(!$('admit').disabled,'execution still separate');
$('logout').click();await until(()=>$('message').textContent==='Signed out.','logout');assert($('selection').hidden&&$('review').hidden&&!$('review-summary').textContent,'logout clears exact review');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
