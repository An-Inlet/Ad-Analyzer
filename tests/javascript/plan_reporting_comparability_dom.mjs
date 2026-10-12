import {renderPlanDocument,clearPlanDocument} from './plan-document.mjs';
import {appendReportingComparability} from './plan-reporting-comparability.mjs';
const host=document.querySelector('#host'),assert=(v,m)=>{if(!v)throw Error(m);};
const opts=p=>({workspaceId:p.inputs.workspace_id,planId:p.inputs.plan_id,freshness:'current'});
const render=(p,extra={},now=Date.parse(p.generated_at))=>renderPlanDocument(host,p,{...opts(p),...extra},now);
try{
 const documents=await (await fetch('/reporting-documents.json')).json();
 for(const [name,plan] of Object.entries(documents)){
  const original=JSON.stringify(plan);render(plan);const pane=host.querySelector('#planning-reporting-comparability');assert(pane,'prominent basis review');
  assert(pane.textContent.includes('Click-through, view-through and report-time basis')&&pane.textContent.includes('Not Qualified Across Accounts'),'attribution and equivalence blockers');
  assert(pane.querySelectorAll('[data-reporting-account]').length===plan.inputs.accounts.length,'exact separate account cards');
  assert(pane.textContent.includes('Requested Primary Period')&&pane.textContent.includes('What Must Be Aligned Or Verified'),'period and recovery');
  assert(!pane.querySelector('a,button,input,img,script'),'no mutations or injected controls');
  for(const action of plan.actions.filter(a=>a.key.startsWith('review:')))assert(pane.textContent.includes(action.rationale),'complete recorded explanation, not parsed metrics');
  const details=[...pane.querySelectorAll('details')];assert(details.every(d=>!d.open),'explicit initial disclosure');details[0].querySelector('summary').click();assert(details[0].open,'usable expand');details[0].querySelector('summary').click();assert(!details[0].open,'usable collapse');details[0].open=true;
  render(plan);assert([...host.querySelectorAll('#planning-reporting-comparability details')].every(d=>!d.open),'repeat clears disclosure state');assert(JSON.stringify(plan)===original,'display never mutates artifact');
  if(['positive','partial','missing','zero','mixed','mixed_partial'].includes(name)){assert(pane.textContent.includes('Recorded Currency: USD')&&pane.textContent.includes('America/New_York'),'saved source currency and timezone');assert(pane.textContent.includes('Aggregate Acquisition Range')&&pane.textContent.includes('not establish complete day coverage'),'capture range is not completeness');assert(pane.textContent.includes('Confirmed Choice Reference'),'source choice trace');}
  if(name==='retained_legacy')assert(pane.textContent.includes('Typed Event And Attribution Metadata: Unavailable'),'legacy metadata remains absent');
  if(name==='retained_typed'){
   assert(pane.textContent.includes('Recorded Selected Event: customers/')&&pane.textContent.includes('Recorded Attribution: Click Unavailable · View Unavailable'),'typed event and explicit unknown attribution');
   const known=structuredClone(plan),pin=known.selected_reporting_proof.accounts.find(a=>a.capture_pin).capture_pin,p=pin.observation_provenance;
   p.attribution={click_window_days:7,view_window_days:0,report_time_basis:'interaction',provenance:'verified_request_contract',producer_contract:p.producer_contract};
   if(p.settings){let blocked=false;try{render(known);}catch{blocked=true;}assert(blocked&&host.hidden,'requested/effective contract refuses invented known settings');render(plan);assert(host.textContent.includes('Requested Settings: action_report_time=Not Sent')&&host.textContent.includes('Effective Settings: Unknown.'),'separate original request and unknown effective settings');}
   else {render(known);assert(host.textContent.includes('Click 7 Days · View 0 Days')&&host.textContent.includes('no cross-account comparability is granted'),'legacy presentation-only known windows keep zero literal');}
   if(p.settings){
    // Presentation-only adversarial DTO: not a qualified Meta report or saved producer artifact.
    const social=structuredClone(plan),replacePlatform=x=>{if(!x||typeof x!=='object')return;for(const k of Object.keys(x)){if(k==='platform'&&x[k]==='google_ads')x[k]='meta_ads';else replacePlatform(x[k]);}};replacePlatform(social);
    const meta=social.selected_reporting_proof.accounts.find(a=>a.capture_pin).capture_pin.observation_provenance;
    Object.assign(meta,{event_namespace:'meta_action_type',native_event_id:'offsite_conversion.fb_pixel_purchase',metric_family:'actions',api_version:'v26.0',capability:'unknown',producer_contract:'unverified.meta.website-purchase.campaign-day.v1'});
    meta.attribution={click_window_days:null,view_window_days:null,report_time_basis:'unknown',provenance:'provider_default_unknown',producer_contract:meta.producer_contract};
    Object.assign(meta.settings,{profile:'meta.website-purchase.campaign-day.v1',count_meaning:'website_purchase_actions',report_support:'unverified',value_unit:'unknown',effective:structuredClone(meta.attribution),requested:{action_report_time:'conversion',use_unified_attribution_setting:true,action_attribution_windows:['7d_click','7d_view','28d_view']}});
    const display=document.createElement('div');appendReportingComparability(display,social,{freshness:'current',now:Date.parse(plan.generated_at)});
    assert(display.textContent.includes('action_report_time=conversion')&&display.textContent.includes('Meta ignores action_report_time')&&display.textContent.includes('Effective Settings: Unknown.')&&display.textContent.includes('Monetary Value: Unavailable')&&!display.textContent.includes('Click 7 Days'),'ignored and retired requests never effective windows or known money units');
    for(const corrupt of [m=>m.settings.value_unit='account_currency_major',m=>m.settings.report_support='existing_google_contract',m=>m.settings.effective.report_time_basis='conversion',m=>m.capability='supported']){const bad=structuredClone(social);corrupt(bad.selected_reporting_proof.accounts.find(a=>a.capture_pin).capture_pin.observation_provenance);let refused=false;try{appendReportingComparability(document.createElement('div'),bad,{freshness:'current',now:Date.parse(plan.generated_at)});}catch{refused=true;}assert(refused,'unverified social presentation fails closed');}
   }
   const missing=structuredClone(plan);delete missing.selected_reporting_proof.accounts.find(a=>a.capture_pin).capture_pin.observation_provenance;let missingRefused=false;try{render(missing);}catch{missingRefused=true;}assert(missingRefused&&host.hidden,'versioned plan cannot lose required metadata');
   for(const corrupt of [p=>p.native_event_owner_id='9999999999',p=>p.native_event_id='generic_total',p=>p.started_at=p.requested_ends_on+'T00:00:00Z']){const bad=structuredClone(plan);corrupt(bad.selected_reporting_proof.accounts.find(a=>a.capture_pin).capture_pin.observation_provenance);let refused=false;try{render(bad);}catch{refused=true;}assert(refused&&host.hidden,'malformed typed event or unclosed capture refused');}
   p.attribution.provenance='provider_default_unknown';let refused=false;try{render(known);}catch{refused=true;}assert(refused&&host.hidden,'unknown cannot carry windows');render(plan);
  }
  if(name==='missing')assert(pane.textContent.includes('selected count unavailable')&&pane.textContent.includes('not full-window zero'),'missing is not zero');
  if(name==='zero')assert(pane.textContent.includes('Observed zero selected conversions across this complete requested window'),'true zero retained');
  if(name==='partial')assert(pane.textContent.includes('Missing or partial selected observations'),'partial retained');
  if(name==='mixed_partial')assert(pane.textContent.includes('1 selected calendar days absent'),'actual omitted raw day');
  if(name.startsWith('mixed'))assert(pane.querySelectorAll('[data-reporting-account]').length===3&&pane.textContent.includes('Meta Ads')&&pane.textContent.includes('TikTok Ads')&&pane.textContent.includes('unsupported_selected_mapping'),'real three-account distinctions');
  if(['legacy','meta','tiktok'].includes(name))assert(pane.textContent.includes('Selected Capture: Unavailable')&&pane.textContent.includes('not substituted'),'legacy/social absence honest');
  render(plan,{freshness:'source_changed'});assert(host.querySelector('#planning-reporting-comparability').textContent.includes('source changed'),'historical status');
  render(plan,{},Date.parse(plan.valid_until));assert(host.querySelector('#planning-reporting-comparability').textContent.includes('expired'),'expiry visible');
  clearPlanDocument(host);assert(host.hidden&&!host.childNodes.length,'session clear');
  for(const corrupt of [
    p=>{p.schema_version='inlet.plan-version.v99';},
    p=>{p.inputs.accounts[0].workspace_id+=100;},
    p=>{p.inputs.accounts.push(p.inputs.accounts[0]);},
    p=>{const e=p.evidence.find(e=>e.account);e.account.connection_id+=100;},
    p=>{p.evidence.push(p.evidence[0]);},
  ]){render(plan);const bad=structuredClone(plan);corrupt(bad);let refused=false;try{render(bad);}catch{refused=true;}assert(refused&&host.hidden&&!host.childNodes.length,'malformed basis clears whole view');}
  if(plan.selected_reporting_proof?.accounts.some(a=>a.capture_pin)){
   for(const corrupt of [p=>p.selected_reporting_proof.accounts[0].capture_pin.aggregate.scope.account_id++,p=>p.selected_reporting_proof.accounts[0].source_fence.source_revision='wrong',p=>p.selected_reporting_proof.accounts[0].selection_head.invalidated=true,p=>{p.selected_reporting_proof.accounts[0].capture_pin=null;p.inputs.selected_reporting=[];},p=>{p.selected_reporting_proof.accounts[0].traffic_pin=null;},p=>{const e=p.evidence.find(e=>e.kind==='reported_metrics');e.observed_at=e.expires_at;}]){const bad=structuredClone(plan);corrupt(bad);let refused=false;try{render(bad);}catch{refused=true;}assert(refused&&host.hidden,'foreign/mismatched pin refused');}
   // Presentation-only DTO variation, not an authenticated currency producer fixture.
   const euro=structuredClone(plan);const original=euro.selected_reporting_proof.accounts.find(a=>a.capture_pin);original.capture_pin.aggregate.scope.currency='EUR';if(original.traffic_pin)original.traffic_pin.aggregate.scope.currency='EUR';render(euro);assert(host.querySelector('#planning-reporting-comparability').textContent.includes('Recorded Currency: EUR'),'never replace recorded currency with USD goal');
  }
  const literal=structuredClone(plan),action=literal.actions.find(a=>a.key.startsWith('review:'));
  if(action){action.rationale='<img src=x onerror=alert(1)> =SUM(A1)';render(literal);assert(host.textContent.includes(action.rationale)&&!host.querySelector('img,script'),'literal explanations');}
 }
 await fetch('/result',{method:'POST',body:'PASS'});
}catch(error){await fetch('/result',{method:'POST',body:error.stack||String(error)});}
