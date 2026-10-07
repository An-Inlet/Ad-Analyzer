import {mountAcquisition} from './commerce-acquisition.mjs';
const base='/api/customer/v1', $=id=>document.getElementById(id);
const node=(tag,value)=>{const result=document.createElement(tag);result.textContent=value;return result;};
let acquisition=null;
let busy=false, signedIn=false, epoch=0, user=null, workspaces=[], comparisonGoals=[], publication=null;
class Stale extends Error {}
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
function clearComparison(){ publication=null; comparisonGoals=[]; $('descriptive-controls').hidden=true; $('descriptive-report').hidden=true; for(const id of ['descriptive-goal','descriptive-values','descriptive-status','descriptive-reasons'])$(id).replaceChildren(); }
function clear(resetAcquisition=true){if(resetAcquisition)acquisition?.clear();clearComparison(); $('measurement-report').hidden=true; for(const id of ['measurement-summary','measurement-basis','measurement-coverage','measurement-limitations','measurement-days'])$(id).replaceChildren(); }
function enable(){for(const id of ['measurement-workspace','measurement-store','measurement-retry','measurement-logout','descriptive-submit','descriptive-goal','descriptive-before-start','descriptive-before-end','descriptive-after-start','descriptive-after-end'])$(id).disabled=busy; $('measurement-load').disabled=busy||!signedIn||!$('measurement-store').value;}
async function api(path,method='GET',body=null) {
  const turn=epoch,cookies=document.cookie;
  const valid=()=>{if(turn!==epoch)throw new Stale();if(cookies!==document.cookie&&!(path==='/session'&&method==='DELETE')){epoch++;signedIn=false;clear();$('measurement-selection').hidden=true;options('measurement-workspace',[],()=> '');options('measurement-store',[],()=> '');throw Object.assign(new Error('Your session changed. Refresh your session.'),{status:401});}};
  const headers={Accept:'application/json'};
  if(method!=='GET') {const csrf=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('__Host-inlet_csrf='))?.split('=')[1]; if(!/^[A-Za-z0-9_-]{43}$/.test(csrf||''))throw Object.assign(new Error('Sign in again.'),{status:401}); headers['X-CSRF-Token']=csrf;}
  if(body!==null)headers['Content-Type']='application/json';
  let response;try{response=await fetch(base+path,{method,headers,...(body===null?{}:{body:JSON.stringify(body)}),credentials:'same-origin',redirect:'error',cache:'no-store'});}catch(error){valid();throw error;}valid();
  if(!response.ok){let failure={};try{failure=await response.json();}catch{}valid();const messages={acquisition_runtime_unavailable:'Shopify window reads are not configured. Existing reads can still be recovered or cancelled.',acquisition_active_conflict:'Another read is still active for this store. Recover your original session’s reads, or return to the session that requested it. Otherwise wait for its deadline and worker cleanup.',acquisition_goal_changed:'The goal changed. Refresh and choose its current confirmed revision.',acquisition_window_unavailable:'Choose a valid window of completed local days within retained history.',acquisition_authority_changed:'Your access or source changed. Refresh your session.'};if(messages[failure.detail])throw Object.assign(new Error(messages[failure.detail]),{status:response.status});throw Object.assign(new Error(({401:'Sign in to view measurements.',403:'Your current access does not allow this view.',409:'The saved goal or source changed. Reload the publication and review the goal.',422:'Check the date windows and select a confirmed goal.',404:'No available completed publication was found. The source may need a completed import, or its history may have been removed.',503:'Measurements are temporarily unavailable.'})[response.status]||'Measurements could not be loaded.'),{status:response.status});}
  let result;try{result=response.status===204?null:await response.json();}catch(error){valid();throw error;}valid();return result;
}
function options(id,rows,label){const placeholder=node('option','Select A Source');placeholder.value='';$(id).replaceChildren(placeholder);for(const row of rows){const option=node('option',label(row));option.value=String(row.id);$(id).append(option);}}
async function stores(){clear();options('measurement-store',[],()=> '');const wid=$('measurement-workspace').value;if(wid)options('measurement-store',await api(`/workspaces/${encodeURIComponent(wid)}/commerce/stores`),s=>`${s.currency} · ${s.time_zone} · ${s.status}`);}
async function session(){clear();signedIn=false;$('measurement-selection').hidden=true;user=(await api('/session')).user_id;signedIn=true;$('measurement-logout').hidden=false;workspaces=await api('/workspaces');options('measurement-workspace',workspaces,w=>w.name);options('measurement-store',[],()=> '');$('measurement-selection').hidden=false;$('measurement-message').textContent='Choose a workspace and Shopify source to view its latest completed import.';}
function render(row){const m=summary(row);clear(false);$('measurement-summary').textContent=`Shopify · As Of ${m.as_of}`;for(const [label,value]of [['Currency',m.currency],['Store Time Zone',m.time_zone],['Source Watermark',m.source_watermark],['Measurement Basis','Net Merchandise Sales'],['Attribution','Store Total — Advertising Attribution Unavailable']])$('measurement-basis').append(node('dt',label),node('dd',value));const complete=m.partitions.filter(p=>p.state.startsWith('complete_')).length;const missing=m.partitions.length-complete;$('measurement-coverage').textContent=`${complete} Complete Days · ${missing} Missing Or Suppressed Days`;$('measurement-limitations').textContent=`Comparison maturity is unavailable. ${row.import_in_progress?'A newer import is still in progress. ':''}${row.stale_source?'This published source is stale. ':''}This is a saved as-of measurement, not a final sales total or verified optimization outcome.`;for(const p of m.partitions){const tr=document.createElement('tr');tr.append(node('td',p.day),node('td',p.state.startsWith('complete_')?money(p.net_sales_micros,m.currency):'Unavailable'),node('td',({complete_zero:'Complete · Zero',complete_nonzero:'Complete',missing:'Missing',suppressed:'Suppressed'})[p.state]));$('measurement-days').append(tr);}$('measurement-report').hidden=false;$('measurement-message').textContent='Completed publication loaded.';}
async function guarded(action){if(busy)return;busy=true;enable();try{await action();}catch(error){if(error instanceof Stale)return;clear(false);if([401,403].includes(error.status)){signedIn=false;acquisition?.clear();$('measurement-selection').hidden=true;$('measurement-logout').hidden=true;options('measurement-workspace',[],()=> '');options('measurement-store',[],()=> '');}$('measurement-message').textContent=error.message||'Measurements unavailable.';}finally{busy=false;enable();}}
export function exactMoney(value,currency) {
  if(typeof value!=='string'||! /^-?\d{1,30}$/.test(value)||! /^[A-Z]{3}$/.test(currency))return 'Unavailable';
  const negative=value.startsWith('-'), n=BigInt(negative?value.slice(1):value), whole=n/1000000n;
  const fraction=(n%1000000n).toString().padStart(6,'0').replace(/0+$/,'').padEnd(2,'0');
  return `${currency} ${negative&&n!==0n?'-':''}${whole}.${fraction}`;
}
async function sameUser(){const current=await api('/session');if(current.user_id!==user){epoch++;signedIn=false;throw Object.assign(new Error('Your signed-in account changed. Refresh your session.'),{status:401});}}
async function prepareComparison(row){
  const wid=$('measurement-workspace').value;
  if(workspaces.find(w=>String(w.id)===wid)?.role!=='owner')return;
  const rows=await api(`/workspaces/${encodeURIComponent(wid)}/goals`);
  comparisonGoals=rows.filter(g=>g.confirmation_recorded&&g.definition?.store_id===row.manifest.store_id);
  options('descriptive-goal',comparisonGoals,g=>`Goal Revision ${g.revision}`);
  publication=row.publication_id;
  $('descriptive-controls').hidden=false;
}
async function compare(){
  $('descriptive-report').hidden=true; $('descriptive-values').replaceChildren();
  const wid=$('measurement-workspace').value, sid=$('measurement-store').value;
  const goal=comparisonGoals.find(g=>g.id===$('descriptive-goal').value);
  if(!goal||!publication)throw new Error('Choose a confirmed goal and load a completed publication.');
  await sameUser();
  const result=await api(`/workspaces/${encodeURIComponent(wid)}/descriptive-comparisons`,'POST',{
    goal_id:goal.id,expected_goal_revision:goal.revision,publication_id:publication,
    before_start:$('descriptive-before-start').value,before_end:$('descriptive-before-end').value,
    after_start:$('descriptive-after-start').value,after_end:$('descriptive-after-end').value,
  });
  await sameUser();
  if(result.schema_version!=='inlet.descriptive-comparison.v1'||result.workspace_id!==Number(wid)||result.goal_id!==goal.id||result.goal_revision!==goal.revision||result.current?.publication_id!==publication||result.before?.source?.source_id!==sid||result.after?.source?.source_id!==sid||result.maturity!=='unqualified'||result.action_attribution!=='unavailable'||result.causal_lift!==null||result.recommendation_update!==null||result.spending_authority!=='none'||!['available_as_of','insufficient'].includes(result.status))throw new Error('Descriptive response could not be verified.');
  const currency=result.before.basis.currency;
  if(result.after.basis.currency!==currency)throw new Error('Comparison currency changed.');
  $('descriptive-status').textContent=result.status==='available_as_of'?'As-Of Descriptive Values Available — Not A Mature Action Outcome':'Insufficient Evidence For A Descriptive Comparison';
  const ratio=result.status==='available_as_of'&&typeof result.relative_difference==='string'&&/^-?\d+(?:\.\d+)?(?:E[+-]?\d+)?$/.test(result.relative_difference)&&result.relative_difference.length<=100?result.relative_difference:'Unavailable (Zero Or Negative Baseline, Or Insufficient Evidence)';
  for(const [label,value]of [['Before',exactMoney(result.before.value,currency)],['After',exactMoney(result.after.value,currency)],['Absolute Difference',result.status==='available_as_of'?exactMoney(result.absolute_difference,currency):'Unavailable'],['Relative Difference (Ratio)',ratio],['Store Time Zone',result.before.basis.time_zone],['Evaluated As Of',result.evaluated_at]])$('descriptive-values').append(node('dt',label),node('dd',value));
  const labels={baseline_zero:'The baseline is zero; relative change is undefined.',baseline_negative:'The baseline is negative; relative change is undefined.',source_revision_changed:'The source changed. Load its latest publication.',source_not_ready:'A source import is incomplete or unavailable.',measurement_coverage_incomplete:'Some requested days are missing or suppressed.',unequal_local_days:'Choose equal numbers of local days.',future_evidence:'Evidence is dated in the future.',stale_source:'The source is stale.',window_not_closed:'A requested window is not complete.',goal_unconfirmed:'Confirm the current goal first.',goal_measurement_basis_mismatch:'Goal measurement basis differs from the store.',measurement_basis_changed:'Measurement basis changed.',correction_unresolved:'Source corrections remain unresolved.'};
  const messages=[...(result.reasons||[]),...(result.warnings||[])].filter(code=>labels[code]).map(code=>labels[code]);
  $('descriptive-reasons').textContent=messages.join(' ')||'Store-total observations may change with later refunds or corrections. No action effect is inferred.';
  $('descriptive-report').hidden=false;
}
if(typeof document!=='undefined'){
acquisition=mountAcquisition({api,sameUser,guarded,selection:()=>({workspace:$('measurement-workspace').value,store:$('measurement-store').value,owner:workspaces.find(w=>String(w.id)===$('measurement-workspace').value)?.role==='owner'})});
$('measurement-retry').onclick=()=>{epoch++;guarded(session);};$('measurement-workspace').onchange=()=>{epoch++;clear();guarded(stores);};$('measurement-store').onchange=()=>{epoch++;clear();enable();acquisition.load().catch(error=>{if(!(error instanceof Stale))$('acquisition-message').textContent=error.message||'Read requests unavailable.';});};$('measurement-load').onclick=()=>guarded(async()=>{clear(false);const wid=$('measurement-workspace').value,sid=$('measurement-store').value;const row=await api(`/workspaces/${encodeURIComponent(wid)}/commerce/stores/${encodeURIComponent(sid)}/publications/latest`);if(row.manifest?.workspace_id!==Number(wid)||row.manifest?.store_id!==sid)throw new Error('Measurement ownership could not be verified.');render(row);await prepareComparison(row);});$('descriptive-form').onsubmit=event=>{event.preventDefault();guarded(compare);};$('measurement-logout').onclick=()=>guarded(async()=>{clear();signedIn=false;acquisition?.clear();$('measurement-selection').hidden=true;$('measurement-logout').hidden=true;options('measurement-workspace',[],()=> '');options('measurement-store',[],()=> '');await api('/session','DELETE');$('measurement-message').textContent='Signed out.';});guarded(session);
}
