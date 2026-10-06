const $ = id => document.getElementById(id);
const assert = (value, message) => { if (!value) throw new Error(message); };
const until = async predicate => { for(let i=0;i<500;i++){if(predicate())return;await new Promise(r=>setTimeout(r,10));} throw new Error('Export DOM timed out'); };
const json = async (path, method='GET', body) => {
  const csrf = document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith('__Host-inlet_csrf='))?.split('=')[1];
  const response = await fetch(path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-Inlet-Request':'1',...(csrf?{'X-CSRF-Token':csrf}:{}),'Idempotency-Key':'browser-export-fixture-request'},...(body?{body:JSON.stringify(body)}:{})});
  assert(response.ok, `${path}: ${response.status}`);
  return response.status===204 ? null : response.json();
};
try {
  await json('/api/customer/v1/session','POST',{id_token:'export-owner:1'});
  const workspace=await json('/api/customer/v1/workspaces','POST',{name:'Browser Export',slug:'browser-export'});
  await import('/app/assets/workspace-export.mjs');
  await until(()=>$('export-workspace').options.length===2);
  $('export-workspace').value=String(workspace.id);$('export-workspace').dispatchEvent(new Event('change'));
  $('export-create').click();await until(()=>!$('export-receipt').hidden);
  const link=$('export-download').getAttribute('href');
  const download=await fetch(link,{credentials:'same-origin'});
  assert(download.status===200 && download.headers.get('content-type').startsWith('application/x-tar'),'Archive response missing');
  const body=new Uint8Array(await download.arrayBuffer());
  const text=new TextDecoder().decode(body);
  assert(body.length>10240 && text.includes('manifest.json') && text.includes('Browser Export'),'Actual database archive missing owned workspace');
  $('export-refresh').click();await until(()=>$('export-state').textContent.includes('Delivery Unconfirmed'));
  assert($('export-snapshot').textContent.includes('All stored records: Incomplete'),'Incomplete data mislabeled');
  await json('/api/customer/v1/session','DELETE');
  $('export-refresh').click();await until(()=>$('export-message').textContent.includes('session ended'));
  assert($('export-receipt').hidden && !$('export-download').hasAttribute('href'),'Logout retained export data');
  assert((await fetch(link,{credentials:'same-origin'})).status===401,'Revoked cookie could export');
  await fetch('/__export_result__',{method:'POST',body:'passed'});
} catch(error) { await fetch('/__export_result__',{method:'POST',body:String(error.stack||error)}); }
