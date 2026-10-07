// Future creation uses the actual linked UI. No legacy policy exemption.
const $=id=>document.getElementById(id),assert=(ok,message)=>{if(!ok)throw Error(message);};
async function until(check,label){const end=Date.now()+20000;while(!check()){if(Date.now()>end)throw Error(label+': '+$('linked-message').textContent);await new Promise(r=>setTimeout(r,30));}}
const change=id=>$(id).dispatchEvent(new Event('change'));
try{
 const login=await fetch('/api/customer/v1/session',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'configured-tiktok:browser'})});assert(login.ok,'actual login');
 const csrf=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('__Host-inlet_csrf='))?.split('=')[1];
 async function post(suffix,body){const r=await fetch('/api/customer/v1/workspaces/__WORKSPACE__/execution'+suffix,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});assert(r.ok,'actual mandate '+r.status);return r.json();}
 const policy=await post('/mandates',__POLICY__);await post(`/mandates/${policy.id}/consent`,{expected_revision:policy.revision,policy_digest:policy.policy_digest});
 await import('/app/assets/tiktok-linked.mjs');await until(()=>!$('linked-selection').hidden&&!$('linked-refresh').disabled,'session');
 $('linked-workspace').value='__WORKSPACE__';change('linked-workspace');await until(()=>[...$('linked-draft').options].some(x=>x.value==='__DRAFT__')&&!$('linked-refresh').disabled,'owned drafts');
 $('linked-draft').value='__DRAFT__';change('linked-draft');$('linked-load').click();await until(()=>!$('linked-configuration').hidden&&!$('linked-refresh').disabled,'actual linked catalog');
 $('linked-option').selectedIndex=1;change('linked-option');$('linked-cover').selectedIndex=1;change('linked-cover');await until(()=>$('execution-linked-media').textContent.includes('Exact Private Media Loaded')&&!$('linked-refresh').disabled,'exact video and cover');
 assert($('execution-linked-media').querySelector('video').readyState>=2,'actual playable video');assert($('execution-linked-media').querySelector('img').naturalWidth>0,'actual decoded cover');
 for(const id of ['linked-pair','linked-rights','linked-post','linked-visibility']){$(id).checked=true;change(id);}
 $('linked-save').click();await until(()=>!$('linked-saved').hidden&&!$('linked-refresh').disabled,'saved linked review');assert($('linked-confirm').disabled,'exact confirmation separate');
 $('linked-confirm-check').checked=true;change('linked-confirm-check');$('linked-confirm').click();await until(()=>!$('linked-spending').hidden&&!$('linked-refresh').disabled,'confirmed configuration');
 $('linked-mandate').value=policy.id;change('linked-mandate');assert($('linked-mandate-summary').textContent.includes('Total Period Limit'),'real mandate schema');$('linked-prepare').click();await until(()=>!$('linked-execution').hidden&&!$('linked-refresh').disabled,'exact linked execution');
 assert($('linked-execution-summary').textContent.includes('Activation Requires Separate Approval'),'paused only');assert($('linked-start').disabled,'approval required');
 $('linked-approve-check').checked=true;change('linked-approve-check');$('linked-approve').click();await until(()=>!$('linked-start').disabled,'exact approval');$('linked-start').click();await until(()=>!$('linked-run').hidden&&!$('linked-refresh').disabled,'saved run');
 location.assign($('linked-run').href);
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
