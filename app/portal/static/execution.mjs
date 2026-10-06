import {clearMedia as removeMedia,showMedia} from './execution-media.mjs';
const $=id=>document.getElementById(id), base='/api/customer/v1';
const text=(tag,value)=>{const n=document.createElement(tag);n.textContent=value;return n;};
const names={google_ads:'Google Ads',meta_ads:'Meta Ads',tiktok_ads:'TikTok Ads'};
const reasons={social_configuration_discovery_unavailable:'Social account configuration could not be verified.',social_native_configuration_unqualified:'Native provider configuration is not qualified. Execution remains blocked.',social_configuration_changed:'The confirmed social configuration changed. Review it again.',new_exact_configuration_review_required:'Create and confirm a new exact social configuration review.',provider_execution_not_configured:'Provider execution is not configured.',named_configuration_catalog_unavailable:'Named account configuration is not available yet.',provider_configuration_producer_unavailable:'Provider configuration discovery is not available yet.',configuration_catalog_unavailable:'Account configuration could not be verified.',configuration_catalog_changed:'Account configuration changed. Refresh and review again.',named_configuration_selection_changed:'The selected configuration changed. Refresh and review again.',separate_execution_consent_required:'Confirm separate execution consent first.',activation_runtime_unavailable:'Activation is not configured.'};
let busy=false, capability=null, context=null, policy=null, reviewed=null, run=null, wid='', signed=false, socialConfigurations=[], generation=0, deferred=null, selectionMediaReady=false, reviewMediaReady=false;
export function micros(value){if(!/^\d+(?:\.\d{1,6})?$/.test(value))throw new Error('Enter a non-negative amount with at most six decimal places.');const [a,b='']=value.split('.');const n=BigInt(a)*1000000n+BigInt(b.padEnd(6,'0'));if(n>1000000000000000n)throw new Error('Amount exceeds the supported limit.');return Number(n);}
const money=(amount,currency)=>Number.isSafeInteger(amount)?new Intl.NumberFormat('en',{style:'currency',currency,maximumFractionDigits:6}).format(amount/1000000):'Unavailable';
const optionRows=(id,rows,label,key='id')=>{const first=text('option','Select…');first.value='';$(id).replaceChildren(first);for(const row of rows){const o=text('option',label(row));o.value=String(row[key]);$(id).append(o);}};
function clearMedia(kind){if(kind==='review')reviewMediaReady=false;else selectionMediaReady=false;removeMedia(kind);}
function clearSelection(){clearMedia('selection');socialConfigurations=[];optionRows('execution-social-catalog',[],r=>r.id);$('execution-social-summary').replaceChildren();}
function invalidateReview(){generation++;reviewed=null;$('execution-review').hidden=true;$('execution-review-check').checked=false;$('execution-review-summary').replaceChildren();clearMedia('review');}
function clear(){invalidateReview();clearMedia('selection');context=policy=reviewed=run=null;socialConfigurations=[];optionRows('execution-social-catalog',[],r=>r.id);for(const id of ['execution-policy','execution-configuration','execution-review','execution-runs'])$(id).hidden=true;for(const id of ['execution-source','execution-policy-summary','execution-review-summary','execution-social-summary','execution-run-state','execution-steps','execution-receipt'])$(id).replaceChildren();$('execution-consent-check').checked=$('execution-review-check').checked=false;}
function enabled(){for(const button of document.querySelectorAll('button'))button.disabled=busy;$('execution-context').disabled=busy||!$('execution-draft').value||!capability?.providers.some(p=>p.available);$('execution-consent').disabled=busy||!policy||!$('execution-consent-check').checked;$('execution-prepare').disabled=busy||policy?.state!=='active'||(context?.draft.artifact.definition.account.platform!=='google_ads'&&!selectionMediaReady);$('execution-revoke').disabled=busy||policy?.state!=='active';$('execution-approve').disabled=busy||!reviewed||!reviewMediaReady||!$('execution-review-check').checked;$('execution-review-check').disabled=busy||!reviewed||!reviewMediaReady;$('execution-consent-check').disabled=busy||!policy;$('execution-logout').disabled=false;$('execution-start').disabled=busy||!reviewed?.approved;$('execution-advance').disabled=busy||!capability?.providers.some(p=>p.available)||!run||['unknown','conflict','canceled','created_paused','activation_observed'].includes(run.state);$('execution-cancel').disabled=busy||!run||run.canceled;$('execution-activate').disabled=busy||run?.state!=='created_paused'||policy?.state!=='active'||!capability?.activation_available;}
const contextFields=['execution-workspace','execution-draft','execution-social-catalog','execution-catalog','execution-daily','execution-bid','execution-partners','execution-total','execution-per-plan','execution-change','execution-actions','execution-cooldown','execution-aggressiveness','execution-run'];
const snapshot=()=>JSON.stringify(contextFields.map(id=>{const e=$(id);return e.type==='checkbox'?e.checked:e.value;}));
const csrf=()=>document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('__Host-inlet_csrf='))?.split('=')[1]||'';
const stale=()=>Object.assign(new Error('Selection changed. Any earlier request may have completed; check saved execution before retrying.'),{stale:true});
async function api(path,method='GET',body){
 const epoch=generation, selection=snapshot(), token=csrf();
 const current=()=>{if(!(path==='/session'&&method==='DELETE')&&token!==csrf())throw Object.assign(stale(),{sessionChanged:true});if(epoch!==generation||selection!==snapshot())throw stale();};
 const headers={Accept:'application/json'};
 if(method!=='GET'){
  if(!/^[A-Za-z0-9_-]{43}$/.test(token))throw Object.assign(new Error('Sign in again.'),{status:401});
  headers['X-CSRF-Token']=token;if(body!==undefined)headers['Content-Type']='application/json';
 }
 const unavailable=()=>Object.assign(new Error(method==='GET'?'The saved status could not be loaded. Refresh to try again.':'The response was lost. The request may have completed; refresh saved status before taking another action.'),{uncertain:method!=='GET'});
 let r;try{r=await fetch(base+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',redirect:'error',cache:'no-store'});}catch{current();throw unavailable();}
 current();let data=null;
 if(r.status!==204){try{data=await r.json();}catch{current();if(r.ok)throw unavailable();}}
 current();
 if(!r.ok){const code=typeof data?.detail==='string'?data.detail:data?.detail?.code;throw Object.assign(new Error(reasons[code]||({401:'Sign in again.',403:'Current owner access is required.',404:'This saved item is unavailable.',409:'The reviewed state changed or execution is blocked. Refresh and review again.',422:'Review the entered settings.'})[r.status]||'Execution request could not be completed.'),{status:r.status});}
 return data;
}
const path=s=>`/workspaces/${encodeURIComponent(wid)}/execution${s}`;
function forgetSession(){clear();signed=false;capability=null;wid='';$('execution-selection').hidden=true;$('execution-logout').hidden=true;for(const id of ['execution-workspace','execution-draft','execution-run','execution-catalog'])optionRows(id,[],x=>x.name);}
function mediaContext(epoch,selection,token){if(token!==csrf()){forgetSession();return false;}return epoch===generation&&selection===snapshot();}
async function guarded(action){
 if(busy)return;busy=true;enabled();
 try{await action();}catch(error){
  if(error.sessionChanged||(!error.stale&&[401,403].includes(error.status)))forgetSession();
  else if(error.uncertain||(!error.stale&&error.status===404)){clear();}
  $('execution-message').textContent=error.message;
 }finally{busy=false;enabled();const next=deferred;deferred=null;if(next)void guarded(next);}
}
function changed(action){invalidateReview();if(busy){deferred=action;enabled();}else void guarded(action);}
function summary(id,items){$(id).replaceChildren();for(const [name,value]of items)$(id).append(text('dt',name),text('dd',String(value)));}
async function session(){clear();signed=false;capability=null;wid='';for(const id of ['execution-workspace','execution-draft','execution-run','execution-catalog'])optionRows(id,[],x=>x.name);await api('/session');signed=true;$('execution-logout').hidden=false;optionRows('execution-workspace',await api('/workspaces'),w=>w.name);$('execution-selection').hidden=false;$('execution-message').textContent='Choose a workspace to review execution availability.';const parts=location.pathname.split('/');if(parts.length===5&&/^\d+$/.test(parts[3])&&/^[a-f0-9]{32}$/.test(parts[4])){wid=parts[3];capability=await api(path('/capabilities'));run=await api(path('/runs/'+parts[4]));await recoverPolicy();renderRun();}}
async function workspace(){clear();wid=$('execution-workspace').value;if(!wid)return;capability=await api(path('/capabilities'));$('execution-environment').textContent=capability.environment==='contract_test'?'Contract Test — No Provider Account Changes':capability.environment==='live'?'Separate Execution Consent And Exact Review Required':'Provider Execution Is Not Configured';$('execution-capabilities').replaceChildren(...capability.providers.map(p=>text('li',`${names[p.platform]}: ${p.available?'Ready For Configuration Review':reasons[p.reason]||'Unavailable'}`)));optionRows('execution-draft',await api(`/workspaces/${wid}/campaign-drafts`),d=>d.name,'draft_id');await loadRuns();}
async function loadRuns(){const rows=await api(path('/runs'));optionRows('execution-run',rows,r=>`${r.purpose==='activate'?'Activation':'Paused Creation'} · ${label(r.state)}`);$('execution-runs').hidden=false;if(run){$('execution-run').value=run.id;renderRun();}}
async function recoverPolicy(){if(run){const rows=await api(path('/mandates'));policy=rows.find(p=>p.id===run.mandate_id&&p.revision===run.mandate_revision&&p.state==='active')||null;}}
const label=s=>String(s).split('_').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join(' ');
function renderRun(){if(!run)return;$('execution-runs').hidden=false;$('execution-run-state').textContent=`${run.environment==='contract_test'?'Contract Test · ':''}${label(run.state)}${run.reservation_retained?' · Exposure Reservation Retained':''}`;$('execution-steps').replaceChildren();for(const step of run.steps){const li=text('li',`${label(step.name)} · ${label(step.state)} `);if(step.attempt_id){const button=text('button','View Receipt');button.onclick=()=>guarded(async()=>{const r=await api(path('/attempts/'+step.attempt_id+'/receipt'));$('execution-receipt').textContent=r.receipt?`${label(r.receipt.outcome)} · ${r.receipt.observed_at} · Effective Time Unavailable`: 'Awaiting Evidence';});li.append(button);if(['unknown','conflict'].includes(step.state)){const check=text('button','Check Original Request');check.onclick=()=>guarded(async()=>{run=await api(path('/runs/'+run.id+'/reconcile'),'POST',{attempt_id:step.attempt_id});renderRun();});li.append(check);}}$('execution-steps').append(li);}history.replaceState(null,'',`/app/execution/${wid}/${run.id}`);}
async function renderReview(){
 const r=reviewed,f=r.configuration,c=r.creative;
 $('execution-review').hidden=false;
 $('execution-review-title').textContent=r.purpose==='activate'?'Separate Activation Review':'Exact Paused Creation Review';
 summary('execution-review-summary',[
  ['Campaign',r.campaign_name],['Platform',names[r.platform]],
  ['Environment',r.environment==='contract_test'?'Contract Test — No Provider Account Changes':'Live'],
  ['Reserved Upper Bound',money(r.reserved_upper_micros,r.currency)],
  ['Campaign Period',`${r.starts_at} to ${r.ends_at}`],['Qualification Expires',r.qualification_expires_at],
  ['Approval',r.purpose==='activate'?'Activation Only After This Separate Approval':'Creates Paused Resources; Activation Requires Another Approval'],
  ['Landing Page',c.landing_page],['Countries',c.audience.countries.join(', ')],['Languages',c.audience.languages.join(', ')]
 ]);
 if(r.platform==='google_ads'){
  summaryAppend('execution-review-summary',[
   ['Average Daily Budget',money(f.daily_budget_micros,r.currency)],['Maximum Cost Per Click',money(f.max_cpc_micros,r.currency)],
   ['Search Partners',f.search_partners?'Included':'Excluded'],['Headlines',c.headlines.join(' · ')],['Descriptions',c.descriptions.join(' · ')],
   ['Exact Keywords',c.exact_keywords.join(' · ')],['Purchase Measurement',`Owned Goal Reference ${f.custom_conversion_goal.split('/').pop()}`]
  ]);
 }else{
  summaryAppend('execution-review-summary',[
   ...configurationIdentity(f),['Campaign Budget',money(f.reservation_micros,r.currency)],['Budget Type','Lifetime'],['Ad Text',c.text],
   ['Call To Action',label(c.call_to_action)],['Media Review',r.platform==='meta_ads'?'Exact Confirmed Image':'Exact Confirmed Video And Cover Pair']
  ]);
  if(r.platform==='meta_ads')summaryAppend('execution-review-summary',[
   ['Headline',c.headline],['Placement','Facebook Feed'],['Age Range',`${f.age_min}–${f.age_max}`],
   ['Special Category','Customer Confirmed None Applicable'],['DSA Names','Not Required By The Reviewed Profile'],
   ['Attribution',f.attribution.map(a=>`${label(a.event_type)} · ${a.window_days} Days`).join(', ')]
  ]);
  else summaryAppend('execution-review-summary',[
   ['Placement','TikTok'],['Age Groups',f.age_groups.map(label).join(', ')],
   ['Click Attribution',label(f.click_attribution_window)],['View Attribution',label(f.view_attribution_window)],
   ['Comments',f.comment_disabled?'Disabled':'Enabled'],['Sharing',f.share_disabled?'Disabled':'Enabled'],['Video Downloads',f.video_download_disabled?'Disabled':'Enabled']
  ]);
 }
 $('execution-review-check').checked=false;
 const epoch=generation,selection=snapshot(),workspace=wid,token=csrf();
 reviewMediaReady=r.platform==='google_ads'||await showMedia('review',workspace,f,()=>mediaContext(epoch,selection,token)&&reviewed===r);
 enabled();
}
function configurationIdentity(c){
 const media=b=>`${b.width} × ${b.height} · File ${b.sha256.slice(0,12)}`;
 return c.image?[['Meta Page',`Owned Reference ${c.page_id}`],['Purchase Pixel',`Owned Reference ${c.pixel_id}`],['Image',media(c.image)]]:
 [['TikTok Identity',`Owned Reference ${c.identity_id}`],['Purchase Pixel',`Owned Reference ${c.tracking_pixel_id}`],['Video',media(c.video)],['Cover Image',media(c.cover)]];
}
function summaryAppend(id,items){for(const [k,v]of items)$(id).append(text('dt',k),text('dd',v));}
if(typeof document!=='undefined'){
for(const id of ['execution-catalog','execution-daily','execution-bid','execution-partners'])for(const event of ['input','change'])$(id).addEventListener(event,()=>{invalidateReview();enabled();});
for(const id of ['execution-total','execution-per-plan','execution-change','execution-actions','execution-cooldown','execution-aggressiveness'])for(const event of ['input','change'])$(id).addEventListener(event,()=>{invalidateReview();clearSelection();policy=null;$('execution-consent-check').checked=false;$('execution-policy-summary').replaceChildren();$('execution-configuration').hidden=true;enabled();});

$('execution-refresh').onclick=()=>changed(session);$('execution-workspace').onchange=()=>{clear();capability=null;wid=$('execution-workspace').value;changed(workspace);};$('execution-draft').onchange=()=>{clear();enabled();};$('execution-context').onclick=()=>guarded(async()=>{context=await api(path('/draft-context'),'POST',{draft_id:$('execution-draft').value});const p=context.proposal;$('execution-policy').hidden=false;$('execution-source').textContent=`${context.draft.artifact.definition.content.name} · ${context.account_names.join(', ')} · ${p.currency} · ${p.time_zone} · ${p.starts_at} to ${p.ends_at}`;for(const [id,value]of [['execution-total',p.total_cap_micros/1000000],['execution-per-plan',p.per_plan_cap_micros/1000000],['execution-change',p.positive_change_cap_micros/1000000],['execution-actions',p.action_limit],['execution-cooldown',p.cooldown_seconds],['execution-aggressiveness',p.aggressiveness_percent]])$(id).value=value;$('execution-message').textContent='Review and edit proposed execution limits. Nothing has been consented.';});
$('execution-policy-form').onsubmit=event=>{event.preventDefault();guarded(async()=>{invalidateReview();clearSelection();$('execution-configuration').hidden=true;const p={...context.proposal,total_cap_micros:micros($('execution-total').value),per_plan_cap_micros:micros($('execution-per-plan').value),positive_change_cap_micros:micros($('execution-change').value),action_limit:Number($('execution-actions').value),cooldown_seconds:Number($('execution-cooldown').value),aggressiveness_percent:Number($('execution-aggressiveness').value)};policy=await api(path('/mandates'),'POST',p);summary('execution-policy-summary',[['Accounts',policy.account_names.join(', ')],['Total Period Limit',money(p.total_cap_micros,p.currency)],['Maximum Per Plan',money(p.per_plan_cap_micros,p.currency)],['Positive Change Limit',money(p.positive_change_cap_micros,p.currency)],['Maximum Actions',p.action_limit],['Cooldown',p.cooldown_seconds+' Seconds'],['Aggressiveness',p.aggressiveness_percent+'% — Does Not Raise Total Limit'],['Allowed Work','Exact Paused Creation And Separately Approved Activation']]);$('execution-consent-check').checked=false;$('execution-message').textContent='Proposed limits saved. Confirm separate consent after reviewing.';});};
$('execution-consent-check').onchange=enabled;$('execution-consent').onclick=()=>guarded(async()=>{invalidateReview();clearSelection();await api(path('/mandates/'+policy.id+'/consent'),'POST',{expected_revision:policy.revision,policy_digest:policy.policy_digest});policy.state='active';if(context.draft.artifact.definition.account.platform!=='google_ads'){
 socialConfigurations=await api(path('/social/confirmed-configurations?draft_id='+encodeURIComponent(context.draft.draft_id)));
 socialConfigurations=socialConfigurations.filter(r=>r.status==='confirmed_historical'&&r.draft_revision===context.draft.revision&&r.environment===capability.environment);
 optionRows('execution-social-catalog',socialConfigurations,r=>`${r.campaign.name} · ${configurationIdentity(r.configuration).map(([k,v])=>`${k}: ${v}`).join(' · ')} · Review ${r.digest.slice(0,12)}`);
 $('execution-google-fields').hidden=true;$('execution-social-fields').hidden=false;$('execution-configuration').hidden=false;
 $('execution-message').textContent=socialConfigurations.length?'Separate consent saved. Select the exact confirmed social configuration.':'Separate consent saved. Review and confirm social configuration before preparing execution.';return;
} $('execution-google-fields').hidden=false;$('execution-social-fields').hidden=true;
const catalog=await api(path('/configuration-options'),'POST',{draft_id:context.draft.draft_id});optionRows('execution-catalog',catalog.options,o=>o.name);$('execution-configuration').hidden=!catalog.options.length;if(!catalog.options.length){$('execution-message').textContent='Separate consent saved, but no supported named purchase measurement is available. Configuration remains blocked.';return;}$('execution-message').textContent='Separate consent saved. Choose named purchase measurement and prepare the exact plan.';});
$('execution-revoke').onclick=()=>guarded(async()=>{await api(path('/mandates/'+policy.id+'/revoke'),'POST');policy.state='revoked';reviewed=null;$('execution-review').hidden=true;$('execution-configuration').hidden=true;$('execution-message').textContent='Execution consent revoked. Existing provider effects and unresolved reservations are unchanged.';});
$('execution-prepare').onclick=()=>guarded(async()=>{invalidateReview();if(context.draft.artifact.definition.account.platform!=='google_ads'){
 const selected=socialConfigurations.find(r=>r.id===$('execution-social-catalog').value);if(!selected)throw new Error('Select an exact confirmed social configuration.');
 reviewed=await api(path('/social/creation-reviews'),'POST',{configuration_review_id:selected.id,expected_configuration_digest:selected.digest,mandate_id:policy.id,mandate_revision:policy.revision});await renderReview();return;
}if(!$('execution-catalog').value)throw new Error('Choose verified purchase measurement.');reviewed=await api(path('/creation-reviews'),'POST',{draft_id:context.draft.draft_id,draft_revision:context.draft.revision,mandate_id:policy.id,mandate_revision:policy.revision,google:{catalog_option_id:$('execution-catalog').value,daily_budget_micros:micros($('execution-daily').value),max_cpc_micros:micros($('execution-bid').value),search_partners:$('execution-partners').checked}});await renderReview();});
$('execution-social-catalog').onchange=()=>{invalidateReview();clearMedia('selection');const r=socialConfigurations.find(r=>r.id===$('execution-social-catalog').value);reviewed=null;$('execution-review').hidden=true;summary('execution-social-summary',r?[['Campaign',r.campaign.name],['Platform',names[r.platform]],...configurationIdentity(r.configuration),['Rules Reviewed',r.requirements_text],['Budget',money(r.configuration.reservation_micros,context.proposal.currency)],['Countries',r.countries.join(', ')],['Languages',r.languages.join(', ')],['Media',r.cover?'Confirmed Video And Cover Pair':'Confirmed Image']]:[]);
 const epoch=generation,selection=snapshot(),workspace=wid,token=csrf();
 if(r)void showMedia('selection',workspace,r.configuration,()=>mediaContext(epoch,selection,token)).then(ready=>{if(epoch===generation&&selection===snapshot()){selectionMediaReady=ready;enabled();}});
 enabled();};
$('execution-review-check').onchange=enabled;$('execution-approve').onclick=()=>guarded(async()=>{const exact=reviewed;await api(path('/reviews/'+exact.id+'/approval'),'POST',{review_digest:exact.review_digest,plan_digest:exact.plan_digest});exact.approved=true;$('execution-message').textContent='Exact plan approved. No execution request has been sent yet.';});$('execution-start').onclick=()=>guarded(async()=>{const exact=reviewed;run=await api(path('/reviews/'+exact.id+'/runs'),'POST');await loadRuns();});$('execution-run').onchange=()=>{clear();changed(async()=>{run=await api(path('/runs/'+$('execution-run').value));await recoverPolicy();renderRun();});};$('execution-advance').onclick=()=>guarded(async()=>{run=await api(path('/runs/'+run.id+'/advance'),'POST');renderRun();});$('execution-cancel').onclick=()=>guarded(async()=>{run=await api(path('/runs/'+run.id+'/cancel'),'POST');renderRun();});$('execution-activate').onclick=()=>guarded(async()=>{invalidateReview();clearMedia('selection');$('execution-configuration').hidden=true;reviewed=await api(path('/activation-reviews'),'POST',{parent_run_id:run.id,mandate_id:policy.id,mandate_revision:policy.revision});await renderReview();});$('execution-logout').onclick=()=>{clear();signed=false;$('execution-selection').hidden=true;$('execution-logout').hidden=true;changed(async()=>{clear();signed=false;for(const id of ['execution-workspace','execution-draft','execution-run','execution-catalog','execution-social-catalog'])optionRows(id,[],w=>w.name);$('execution-selection').hidden=true;$('execution-logout').hidden=true;await api('/session','DELETE');$('execution-message').textContent='Signed out.';});};guarded(session);
}
