import {clearMedia, showMedia} from './execution-media.mjs';
const $ = id => document.getElementById(id), base = '/api/customer/v1';
const checks = ['linked-pair', 'linked-rights', 'linked-post', 'linked-visibility'];
const text = (tag, value) => { const n = document.createElement(tag); n.textContent = String(value); return n; };
let sessionToken = null;
let epoch = 0, busy = false, signed = false, wid = '', drafts = [], draft = null, catalog = [], library = [], primary = null;
let saved = null, mandates = [], exact = null, approved = false, ready = false, exactReady = false;
const csrf = () => document.cookie.split(';').map(x => x.trim()).find(x => x.startsWith('__Host-inlet_csrf='))?.split('=')[1] || '';
const path = suffix => `/workspaces/${encodeURIComponent(wid)}/execution${suffix}`;
const linked = suffix => path('/tiktok/linked' + suffix);
const snapshot = () => [wid, ...['linked-workspace','linked-draft','linked-option','linked-cover','linked-mandate'].map(id => $(id).value)].join('|');
const stale = () => Object.assign(new Error('Selection or session changed. Review the current settings again.'), {stale:true});
function options(id, rows, label, key = 'id') {
  const first = text('option','Choose…'); first.value = ''; $(id).replaceChildren(first);
  for (const row of rows) { const n = text('option',label(row)); n.value = String(row[key]); n.disabled = row.review_available === false; $(id).append(n); }
}
function summary(id, rows) { $(id).replaceChildren(); for (const [key,value] of rows) $(id).append(text('dt',key),text('dd',value)); }
const money = (n,currency) => Number.isSafeInteger(n) && /^[A-Z]{3}$/.test(currency) ? `${(BigInt(n)/1000000n).toString()}.${(BigInt(n)%1000000n).toString().padStart(6,'0')} ${currency}` : 'Unavailable';
function clearExecution() {
  exact = null; approved = false; exactReady = false; clearMedia('linked-review');
  $('linked-execution').hidden = true; $('linked-execution-summary').replaceChildren(); $('linked-approve-check').checked = false; $('linked-run').hidden = true; $('linked-run').removeAttribute('href');
}
function clearReview(media = false) {
  epoch++; saved = null; clearExecution(); $('linked-saved').hidden = true; $('linked-spending').hidden = true;
  $('linked-summary').replaceChildren(); $('linked-confirm-check').checked = false;
  if (media) { ready = false; clearMedia('linked'); for (const id of checks) $(id).checked = false; }
}
function forget() {
  clearReview(true); signed = false; sessionToken = null; wid = ''; draft = null; drafts = []; catalog = []; library = []; primary = null; mandates = [];
  for (const id of ['linked-selection','linked-configuration','linked-logout']) $(id).hidden = true;
  for (const id of ['linked-workspace','linked-draft','linked-option','linked-cover','linked-mandate']) options(id,[],x=>x.name);
}
function enable() {
  for (const el of document.querySelectorAll('button,select,input')) el.disabled = busy;
  $('linked-load').disabled = busy || !signed || !$('linked-draft').value;
  $('linked-save').disabled = busy || !ready || !catalog.find(o=>o.id===$('linked-option').value)?.review_available || !checks.every(id=>$(id).checked);
  $('linked-confirm').disabled = busy || !saved || saved.confirmed || !ready || !$('linked-confirm-check').checked;
  $('linked-prepare').disabled = busy || !saved?.confirmed || !mandates.find(m=>m.id===$('linked-mandate').value);
  $('linked-approve').disabled = busy || !exact || approved || !exactReady || !$('linked-approve-check').checked;
  $('linked-start').disabled = busy || !exact || !approved || !exactReady;
}
async function api(url, method = 'GET', body) {
  const before = epoch, selection = snapshot(), token = csrf();
  if (signed && token !== sessionToken) { forget(); throw Object.assign(new Error('Your original session changed. Refresh your session.'),{status:401}); }
  if (method !== 'GET' && !/^[A-Za-z0-9_-]{43}$/.test(token)) throw Object.assign(new Error('Sign in again.'),{status:401});
  const headers = {Accept:'application/json'};
  if (method !== 'GET') { headers['Content-Type']='application/json'; headers['X-CSRF-Token']=token; }
  const r = await fetch(base+url,{method,headers,credentials:'same-origin',redirect:'error',cache:'no-store',body:body===undefined?undefined:JSON.stringify(body)});
  const bodyText = await r.text();
  if (token !== csrf()) { forget(); throw stale(); }
  if (before !== epoch || selection !== snapshot()) throw stale();
  if (!r.ok) throw Object.assign(new Error(({401:'Sign in again.',403:'Current owner access is required.',404:'The owned record is unavailable.',409:'The source, consent or provider configuration changed. Refresh and review again.',422:'Complete the requested settings and explicit confirmations.',503:'Linked configuration or execution is not configured. No provider changes were made.'})[r.status] || 'The request could not be confirmed. Refresh before continuing.'),{status:r.status});
  return r.status===204?null:JSON.parse(bodyText);
}
async function guarded(action) {
  if (busy) return; busy=true; enable();
  try { await action(); } catch(error) {
    if ([401,403].includes(error.status)) forget(); else clearReview(true);
    $('linked-message').textContent = error.message;
  } finally { busy=false; enable(); }
}
async function media(configuration, kind = 'linked') {
  const before=epoch, selection=snapshot(), token=csrf();
  const current=()=>{ if(token!==csrf()){forget();return false;} return before===epoch&&selection===snapshot(); };
  const ok=await showMedia(kind,wid,configuration,current);
  if(current()) { if(kind==='linked') ready=ok; else exactReady=ok; }
}
function configurationSummary(f,c) {
  return [['Ad Text',c.text],['Landing Page',c.landing_page],['Countries',c.audience.countries.join(', ')],['Languages',c.audience.languages.join(', ')],['Age Groups',f.age_groups.join(', ')],['Account Time Zone',f.account_timezone],['Budget Meaning','Lifetime Budget; Not An Independent Hard Spending Cap'],['Placement','TikTok Only'],['Objective','Website Purchases'],['Attribution',`Click: ${f.click_attribution_window}; View: ${f.view_attribution_window}; Engaged View: ${f.engaged_view_attribution_window}`],['Comments / Sharing / Downloads',`${f.comment_disabled?'Disabled':'Enabled'} / ${f.share_disabled?'Disabled':'Enabled'} / ${f.video_download_disabled?'Disabled':'Enabled'}`],['Audience / Interest / Search Expansion','Disabled'],['Bidding And Delivery','No Bid · Smooth Pacing'],['Offsite Tracking URLs','None']];
}
function showSaved(r) {
  if (r.environment!=='contract_test' || !/^[a-f0-9]{32}$/.test(r.id) || !/^[a-f0-9]{64}$/.test(r.digest) || r.option_id!==$('linked-option').value || r.spending_authority!=='none' || r.financial_qualification!=='not_assessed') throw new Error('The exact linked review could not be verified.');
  const selectedCover=library.find(row=>row.media_id===$('linked-cover').value);
  for(const [actual,expected] of [[r.media?.video,primary],[r.media?.cover,selectedCover]]) {
    if(!actual||!expected||['media_id','sha256','mime','byte_size','width','height'].some(key=>actual[key]!==expected[key]))throw new Error('Saved media differs from the exact reviewed pair.');
  }
  if(r.configuration?.kind!=='tiktok_linked_push_v13'||typeof r.identity_label!=='string'||!r.identity_label.trim())throw new Error('The saved identity and settings are unavailable.');
  saved=r;
  summary('linked-summary', [['Campaign',r.campaign.name],['Environment','Contract Test · No Provider Account Changes'],['Requirements',r.requirements_text],['Linked Identity',r.identity_label],['Identity Type',r.identity_type],...configurationSummary(r.configuration,r.creative),['Visibility',r.visibility],['Post',r.creation],['Campaign Period',`${r.campaign.starts_at} to ${r.campaign.ends_at}`],['Campaign Budget',money(r.campaign.budget_micros,r.campaign.currency)],['Spending Authority','None From Configuration Confirmation'],['Status',r.confirmed?'Confirmed · Separate Execution Approval Required':'Awaiting Exact Confirmation']]);
  $('linked-confirm-check').checked=false; $('linked-saved').hidden=false;
}
async function session() {
  forget(); await api('/session'); sessionToken=csrf(); signed=true; options('linked-workspace',await api('/workspaces'),w=>w.name);
  $('linked-selection').hidden=false; $('linked-logout').hidden=false; $('linked-message').textContent='Choose a workspace and approved TikTok video campaign.';
}
async function workspace() {
  clearReview(true); draft=null; catalog=[]; $('linked-configuration').hidden=true; wid=$('linked-workspace').value;
  options('linked-draft',[],x=>x.name);
  if(wid){drafts=await api(`/workspaces/${wid}/campaign-drafts`);options('linked-draft',drafts,x=>x.name,'draft_id');}
}
function selectedChanged(mediaToo=false) { clearReview(mediaToo); enable(); }
$('linked-refresh').onclick=()=>guarded(session);
$('linked-workspace').onchange=()=>{ clearReview(true); void guarded(workspace); };
$('linked-draft').onchange=()=>{ selectedChanged(true); $('linked-configuration').hidden=true; };
$('linked-load').onclick=()=>guarded(async()=>{
  clearReview(true); draft=drafts.find(d=>d.draft_id===$('linked-draft').value); if(!draft)throw new Error('Choose an approved campaign.');
  const c=await api(linked('/options'),'POST',{draft_id:draft.draft_id,draft_revision:draft.revision});
  if(c.environment!=='contract_test'||!Array.isArray(c.options))throw new Error('Supported linked configuration is unavailable.');
  catalog=c.options;options('linked-option',catalog,o=>o.name);
  const preview=await api(`/workspaces/${wid}/campaign-drafts/${draft.draft_id}/preview`);
  if(preview.artifact.definition.account.platform!=='tiktok_ads')throw new Error('Choose a TikTok video campaign.');
  primary=preview.artifact.definition.content.media;
  library=(await api(`/workspaces/${wid}/media`)).map(row=>({...row,byte_size:row.size}));
  primary=library.find(row=>row.media_id===primary.media_id&&row.sha256===primary.sha256);
  if(!primary||primary.mime!=='video/mp4')throw new Error('The original private video is unavailable.');
  options('linked-cover',library.filter(row=>row.mime.startsWith('image/')),row=>`Image · ${row.width} × ${row.height} · File ${row.sha256.slice(0,12)}`,'media_id');
  $('linked-environment').textContent='Contract Test · No Provider Account Changes'; $('linked-requirements').textContent='Select an exact named configuration to read its requirements.';
  $('linked-configuration').hidden=false; $('linked-message').textContent=c.options.length?'Review the linked identity, video, cover and declarations. Financial qualification remains separate.':'No eligible linked configuration is available.';
});
$('linked-option').onchange=()=>{selectedChanged(true);$('linked-cover').value='';$('linked-requirements').textContent=catalog.find(o=>o.id===$('linked-option').value)?.requirements_text||'Select a configuration.';};
$('linked-cover').onchange=()=>{clearReview(true);void guarded(async()=>{const cover=library.find(x=>x.media_id===$('linked-cover').value);if(primary&&cover)await media({video:primary,cover});});};
for(const id of checks)$(id).onchange=()=>{clearReview();enable();};
$('linked-save').onclick=()=>guarded(async()=>{
  if(!ready||!checks.every(id=>$(id).checked))throw new Error('Review the media and every declaration.');
  showSaved(await api(linked('/reviews'),'POST',{draft_id:draft.draft_id,draft_revision:draft.revision,option_id:$('linked-option').value,cover_media_id:$('linked-cover').value,answer:{kind:'tiktok_linked_push',reviewed_video_and_cover:true,commercial_music_rights_reviewed:true,creates_new_linked_post_reviewed:true,ads_only_visibility_reviewed:true}}));
});
$('linked-confirm-check').onchange=enable;
$('linked-confirm').onclick=()=>guarded(async()=>{
  showSaved(await api(linked(`/reviews/${saved.id}/confirmation`),'POST',{expected_digest:saved.digest,acknowledged:true}));
  mandates=(await api(path('/mandates'))).filter(m=>m.state==='active'&&m.policy?.environment==='contract_test');
  options('linked-mandate',mandates,m=>`Mandate ${m.id.slice(0,12)} · Revision ${m.revision}`);$('linked-spending').hidden=false;$('linked-message').textContent='Configuration confirmed. No ads were published. Select separately consented spending limits.';
});
$('linked-mandate').onchange=()=>{
  epoch++;clearExecution();const m=mandates.find(x=>x.id===$('linked-mandate').value),p=m?.policy;
  summary('linked-mandate-summary',m?[['Accounts',m.account_names.join(', ')],['Total Period Limit',money(p.total_cap_micros,p.currency)],['Per Plan Limit',money(p.per_plan_cap_micros,p.currency)],['Period',`${p.starts_at} to ${p.ends_at}`],['Consent','Existing Consent; This Selection Does Not Raise Any Limit']]:[]);enable();
};
$('linked-prepare').onclick=()=>guarded(async()=>{
  clearExecution();const m=mandates.find(x=>x.id===$('linked-mandate').value);
  const r=await api(linked('/creation-reviews'),'POST',{configuration_review_id:saved.id,expected_configuration_digest:saved.digest,mandate_id:m.id,mandate_revision:m.revision});
  if(r.platform!=='tiktok_ads'||r.environment!=='contract_test'||r.purpose!=='create_paused'||r.configuration.kind!=='tiktok_linked_push_v13')throw new Error('The exact linked execution plan is unavailable.');
  exact=r;const f=r.configuration,c=r.creative;
  summary('linked-execution-summary', [['Campaign',r.campaign_name],['Environment','Contract Test · No Provider Account Changes'],['Reservation',money(r.reserved_upper_micros,r.currency)],['Campaign Period',`${r.starts_at} to ${r.ends_at}`],['Qualification Expires',r.qualification_expires_at],['Linked Identity',`Owned Reference ${f.identity.identity_id}`],['Purchase Pixel',`Owned Reference ${f.pixel_id}`],['Ad Text',c.text],['Landing Page',c.landing_page],['Countries',c.audience.countries.join(', ')],['Languages',c.audience.languages.join(', ')],['Age Groups',f.age_groups.join(', ')],['Attribution',`Click: ${f.click_attribution_window}; View: ${f.view_attribution_window}; Engaged View: ${f.engaged_view_attribution_window}`],['Comments / Sharing / Downloads',`${f.comment_disabled?'Disabled':'Enabled'} / ${f.share_disabled?'Disabled':'Enabled'} / ${f.video_download_disabled?'Disabled':'Enabled'}`],['New Post Visibility','Ads Only'],['Approval','Paused Creation Only; Activation Requires Separate Approval']]);
  $('linked-execution').hidden=false;await media(f,'linked-review');
});
$('linked-approve-check').onchange=enable;
$('linked-approve').onclick=()=>guarded(async()=>{if(!exactReady||!$('linked-approve-check').checked)throw new Error('Review the exact media and plan.');await api(path(`/reviews/${exact.id}/approval`),'POST',{review_digest:exact.review_digest,plan_digest:exact.plan_digest});approved=true;$('linked-message').textContent='Exact paused plan approved. No execution request has been sent.';});
$('linked-start').onclick=()=>guarded(async()=>{if(!approved)throw new Error('Separate exact approval is required.');const run=await api(path(`/reviews/${exact.id}/runs`),'POST');if(!/^[a-f0-9]{32}$/.test(run.id))throw new Error('Saved run is unavailable.');approved=false;$('linked-run').href=`/app/execution/${encodeURIComponent(wid)}/${run.id}`;$('linked-run').hidden=false;$('linked-message').textContent='Execution run saved. Open it to explicitly advance paused creation; activation requires another approval.';});
$('linked-logout').onclick=()=>{forget();void guarded(async()=>{await api('/session','DELETE');$('linked-message').textContent='Signed out.';});};
addEventListener('pagehide',()=>forget());
void guarded(session);
