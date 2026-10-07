const $=id=>document.getElementById('opt-'+id),assert=(v,m)=>{if(!v)throw Error(m);};
const until=async(test,label)=>{const end=Date.now()+20000;while(!test()){if(Date.now()>end)throw Error(label+' '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
try{
if(location.search.includes('review=')){
 await import('/app/assets/optimization.mjs');await until(()=>!$('review').hidden&&!$('refresh').disabled,'ordinary exact review');assert($('admit').disabled,'approval remains separate');$('review-check').checked=true;$('review-check').dispatchEvent(new Event('change'));$('approve').click();await until(()=>!$('admit').disabled,'separate explicit approval');await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}else{
 assert((await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'configured-google:browser'})})).ok,'real login');
 await import('/app/assets/optimization.mjs');await until(()=>$('workspace').options.length===2&&!$('refresh').disabled,'session');$('workspace').value='__WORKSPACE__';$('workspace').dispatchEvent(new Event('change'));await until(()=>!$('candidate-load').disabled&&!$('refresh').disabled,'workspace');
 $('candidate-load').click();await until(()=>$('candidate-policy').options.length===2&&$('candidate-mandate').options.length===2&&!$('refresh').disabled,'named options');$('candidate-policy').selectedIndex=1;$('candidate-policy').dispatchEvent(new Event('change'));$('candidate-mandate').selectedIndex=1;$('candidate-mandate').dispatchEvent(new Event('change'));$('candidate-read').click();await until(()=>$('candidate-progress').textContent.includes('requested')&&!$('refresh').disabled,'enqueued');assert($('candidate-read').disabled,'no accidental repeated enqueue');
 $('candidate-refresh').click();await until(()=>$('candidate-results').textContent.includes('Waiting For Worker')&&!$('refresh').disabled,'actual pending');assert(!$('candidate-results').querySelector('button'),'no premature review');
 assert((await fetch('/__fixture__/tick')).ok,'actual scoped worker');$('candidate-refresh').click();await until(()=>$('candidate-results').textContent.includes('Read Completed')&&!$('refresh').disabled,'completed');
 if('__MODE__'==='scenario'){
  assert($('candidate-results').textContent.includes('Offline Contract Scenario — Fixture Qualification, Not Live Evidence'),'honest fixture qualification');$('candidate-results').querySelector('button').click();await until(()=>$('candidate-results').querySelector('a')&&!$('refresh').disabled,'review prepared only');location.href=$('candidate-results').querySelector('a').href;
 }else{
  assert($('candidate-results').textContent.includes('Evidence Unqualified')&&$('candidate-results').textContent.includes('not qualified'),'blocked reason');assert(!$('candidate-results').querySelector('button'),'no review without evidence');await fetch('/__fixture__/revoke');$('candidate-refresh').click();await until(()=>$('selection').hidden,'revocation clears session');assert($('candidate-results').children.length===0,'cleared owned results');await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
 }
}
}catch(e){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:String(e)})});}
