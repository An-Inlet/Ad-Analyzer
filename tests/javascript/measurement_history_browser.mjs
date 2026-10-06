const $=id=>document.getElementById(id);
const assert=(ok,message)=>{if(!ok)throw new Error(message);};
const until=async(test,message)=>{const end=Date.now()+15000;while(!test()){if(Date.now()>end)throw new Error(message);await new Promise(r=>setTimeout(r,20));}};
try {
  const login=await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'measurement-owner:browser'})});
  assert(login.ok,'actual customer login');
  await import('/app/assets/measurement-history.mjs');
  await until(()=>$('measurement-workspace').options.length===2&&!$('measurement-workspace').disabled,'owned workspace');
  assert($('measurement-workspace').textContent.includes('<img src=x>')&&!document.querySelector('img'),'literal escaped workspace name');
  $('measurement-workspace').value='__WORKSPACE__';$('measurement-workspace').dispatchEvent(new Event('change'));
  await until(()=>$('measurement-store').options.length===2&&!$('measurement-store').disabled,'owned store');
  $('measurement-store').selectedIndex=1;$('measurement-store').dispatchEvent(new Event('change'));$('measurement-load').click();
  await until(()=>!$('measurement-report').hidden&&!$('measurement-load').disabled,'actual terminal publication');
  assert($('measurement-summary').textContent.includes('Shopify · As Of'),'actual publication timestamp');
  assert($('measurement-basis').textContent.includes('USD')&&$('measurement-basis').textContent.includes('Store Time Zone'),'currency and calendar basis');
  assert($('measurement-days').textContent.includes('$90.00')&&$('measurement-days').textContent.includes('Complete · Zero'),'actual sales and confirmed zeros');
  assert($('measurement-coverage').textContent.includes('Complete Days'),'coverage summary');
  assert($('measurement-limitations').textContent.includes('maturity is unavailable'),'truthful maturity gap');
  await fetch('/__fixture__/erase',{method:'POST'});$('measurement-load').click();
  await until(()=>$('measurement-report').hidden&&$('measurement-message').textContent.includes('No available completed publication'),'erased publication hidden');
  assert(!$('measurement-days').textContent,'erased values cleared');
  $('measurement-logout').click();await until(()=>$('measurement-message').textContent==='Signed out.','logout');
  assert($('measurement-selection').hidden&&!$('measurement-workspace').textContent.includes('<img'),'logout clears names');
  assert((await fetch('/api/customer/v1/session')).status===401,'actual session revoked');
  await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
} catch(error) {await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
