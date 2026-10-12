import {renderPlanDocument,clearPlanDocument} from './plan-document.mjs';
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
