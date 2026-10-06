const base='/api/customer/v1', $=id=>document.getElementById(id);
const node=(tag,value)=>{const result=document.createElement(tag);result.textContent=value;return result;};
let busy=false, signedIn=false;
export function money(micros,currency) {
  if(!Number.isSafeInteger(micros)||!/^[A-Z]{3}$/.test(currency)) return 'Unavailable';
  return new Intl.NumberFormat('en',{style:'currency',currency}).format(micros/1000000);
}
export function summary(row) {
  const manifest=row?.manifest;
  if(manifest?.schema_version!=='inlet.commerce-publication.v1'||!Array.isArray(manifest.partitions)||manifest.partitions.length>400||manifest.maturity!=='unavailable') throw new Error('Unsupported measurement publication.');
  if(!/^[A-Z]{3}$/.test(manifest.currency)||typeof manifest.time_zone!=='string'||typeof manifest.as_of!=='string') throw new Error('Measurement basis unavailable.');
  const seen=new Set();
  for(const p of manifest.partitions) {
    if(!/^\d{4}-\d{2}-\d{2}$/.test(p.day)||seen.has(p.day)||!['complete_zero','complete_nonzero','missing','suppressed'].includes(p.state)) throw new Error('Measurement coverage unavailable.');
    seen.add(p.day);
  }
  return manifest;
}
function clear(){ $('measurement-report').hidden=true; for(const id of ['measurement-summary','measurement-basis','measurement-coverage','measurement-limitations','measurement-days'])$(id).replaceChildren(); }
function enable(){for(const id of ['measurement-workspace','measurement-store','measurement-retry','measurement-logout'])$(id).disabled=busy; $('measurement-load').disabled=busy||!signedIn||!$('measurement-store').value;}
async function api(path,method='GET') {
  const headers={Accept:'application/json'};
  if(method!=='GET') {const csrf=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('__Host-inlet_csrf='))?.split('=')[1]; if(!/^[A-Za-z0-9_-]{43}$/.test(csrf||''))throw Object.assign(new Error('Sign in again.'),{status:401}); headers['X-CSRF-Token']=csrf;}
  const response=await fetch(base+path,{method,headers,credentials:'same-origin',redirect:'error',cache:'no-store'});
  if(!response.ok)throw Object.assign(new Error(({401:'Sign in to view measurements.',403:'Your current access does not allow this view.',404:'No available completed publication was found. The source may need a completed import, or its history may have been removed.',503:'Measurements are temporarily unavailable.'})[response.status]||'Measurements could not be loaded.'),{status:response.status});
  return response.status===204?null:response.json();
}
function options(id,rows,label){const placeholder=node('option','Select A Source');placeholder.value='';$(id).replaceChildren(placeholder);for(const row of rows){const option=node('option',label(row));option.value=String(row.id);$(id).append(option);}}
async function stores(){clear();options('measurement-store',[],()=> '');const wid=$('measurement-workspace').value;if(wid)options('measurement-store',await api(`/workspaces/${encodeURIComponent(wid)}/commerce/stores`),s=>`${s.currency} · ${s.time_zone} · ${s.status}`);}
async function session(){clear();signedIn=false;$('measurement-selection').hidden=true;await api('/session');signedIn=true;$('measurement-logout').hidden=false;options('measurement-workspace',await api('/workspaces'),w=>w.name);options('measurement-store',[],()=> '');$('measurement-selection').hidden=false;$('measurement-message').textContent='Choose a workspace and Shopify source to view its latest completed import.';}
function render(row){const m=summary(row);clear();$('measurement-summary').textContent=`Shopify · As Of ${m.as_of}`;for(const [label,value]of [['Currency',m.currency],['Store Time Zone',m.time_zone],['Source Watermark',m.source_watermark],['Measurement Basis','Net Merchandise Sales'],['Attribution','Store Total — Advertising Attribution Unavailable']])$('measurement-basis').append(node('dt',label),node('dd',value));const complete=m.partitions.filter(p=>p.state.startsWith('complete_')).length;const missing=m.partitions.length-complete;$('measurement-coverage').textContent=`${complete} Complete Days · ${missing} Missing Or Suppressed Days`;$('measurement-limitations').textContent=`Comparison maturity is unavailable. ${row.import_in_progress?'A newer import is still in progress. ':''}${row.stale_source?'This published source is stale. ':''}This is a saved as-of measurement, not a final sales total or verified optimization outcome.`;for(const p of m.partitions){const tr=document.createElement('tr');tr.append(node('td',p.day),node('td',p.state.startsWith('complete_')?money(p.net_sales_micros,m.currency):'Unavailable'),node('td',({complete_zero:'Complete · Zero',complete_nonzero:'Complete',missing:'Missing',suppressed:'Suppressed'})[p.state]));$('measurement-days').append(tr);}$('measurement-report').hidden=false;$('measurement-message').textContent='Completed publication loaded.';}
async function guarded(action){if(busy)return;busy=true;enable();try{await action();}catch(error){clear();if([401,403].includes(error.status)){signedIn=false;$('measurement-selection').hidden=true;$('measurement-logout').hidden=true;options('measurement-workspace',[],()=> '');options('measurement-store',[],()=> '');}$('measurement-message').textContent=error.message||'Measurements unavailable.';}finally{busy=false;enable();}}
if(typeof document!=='undefined'){
$('measurement-retry').onclick=()=>guarded(session);$('measurement-workspace').onchange=()=>guarded(stores);$('measurement-store').onchange=()=>{clear();enable();};$('measurement-load').onclick=()=>guarded(async()=>{clear();const wid=$('measurement-workspace').value,sid=$('measurement-store').value;const row=await api(`/workspaces/${encodeURIComponent(wid)}/commerce/stores/${encodeURIComponent(sid)}/publications/latest`);if(row.manifest?.workspace_id!==Number(wid)||row.manifest?.store_id!==sid)throw new Error('Measurement ownership could not be verified.');render(row);});$('measurement-logout').onclick=()=>guarded(async()=>{clear();signedIn=false;$('measurement-selection').hidden=true;$('measurement-logout').hidden=true;options('measurement-workspace',[],()=> '');options('measurement-store',[],()=> '');await api('/session','DELETE');$('measurement-message').textContent='Signed out.';});guarded(session);
}
