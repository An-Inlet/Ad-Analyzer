// Saved-version display only. Never reconstruct event metadata from prose or current settings.
const platforms={google_ads:'Google Ads',meta_ads:'Meta Ads',tiktok_ads:'TikTok Ads'};
const positive=x=>Number.isSafeInteger(x)&&x>0;
const bounded=(x,max=2000)=>typeof x==='string'&&x.length>0&&x.length<=max;
const digest=x=>typeof x==='string'&&/^[a-f0-9]{64}$/.test(x);
const id=x=>typeof x==='string'&&/^[a-f0-9]{32}$/.test(x);
const fail=()=>{throw Error('The saved reporting basis could not be verified. Read the plan again.');};
function accountKey(a){
  if(!a||!positive(a.workspace_id)||!positive(a.account_id)||!positive(a.connection_id)||!Object.hasOwn(platforms,a.platform)||!bounded(a.connection_version,200))fail();
  return JSON.stringify([a.workspace_id,a.account_id,a.connection_id,a.platform,a.connection_version]);
}
function instant(value){if(typeof value!=='string'||!Number.isFinite(Date.parse(value)))fail();return Date.parse(value);}
function period(value){if(!value||instant(value.starts_at)>=instant(value.ends_at_exclusive))fail();return `${new Date(value.starts_at).toISOString()} → ${new Date(value.ends_at_exclusive).toISOString()} (End Exclusive, UTC)`;}
const samePeriod=(a,b)=>a&&b&&instant(a.starts_at)===instant(b.starts_at)&&instant(a.ends_at_exclusive)===instant(b.ends_at_exclusive);
const sameFence=(a,b)=>a&&b&&accountKey(a.account)===accountKey(b.account)&&a.source_revision===b.source_revision&&a.privacy_revision===b.privacy_revision&&a.source_binding_digest===b.source_binding_digest;
function captureSettings(p,scope){
  const s=p.settings;
  if((p.schema_version==='inlet.selected-observation-provenance.v2')!==(s!=null))fail();
  if(s==null)return null;
  const profiles={
    'google.conversions.campaign-day.v1':['google_ads','v24','conversions','selected_action_count',null],
    'google.all-conversions.campaign-day.v1':['google_ads','v24','all_conversions','selected_action_count',null],
    'meta.website-purchase-count.campaign-day.v1':['meta_ads','v26.0','actions','website_purchase_actions','offsite_conversion.fb_pixel_purchase'],
    'meta.website-purchase.campaign-day.v1':['meta_ads','v26.0','actions','website_purchase_actions','offsite_conversion.fb_pixel_purchase'],
    'meta.website-lead.campaign-day.v1':['meta_ads','v26.0','actions','website_lead_actions','offsite_conversion.fb_pixel_lead'],
    'tiktok.website-payment.campaign-day.v1':['tiktok_ads','v1.3','event_count','website_purchase_actions','complete_payment'],
  };
  const expected=profiles[s.profile],r=s.requested,e=s.effective;
  if(!expected||s.schema_version!=='inlet.capture-settings.v1'||expected[0]!==scope.platform||expected[1]!==p.api_version||expected[2]!==p.metric_family||expected[3]!==s.count_meaning||(expected[4]!==null&&expected[4]!==p.native_event_id)||p.native_event_owner_id!==scope.native_account_id)fail();
  if(!r||!e||!['impression','conversion','mixed',null].includes(r.action_report_time)||![true,false,null].includes(r.use_unified_attribution_setting)||!Array.isArray(r.action_attribution_windows)||r.action_attribution_windows.length>6||new Set(r.action_attribution_windows).size!==r.action_attribution_windows.length||r.action_attribution_windows.some(w=>!['1d_click','7d_click','28d_click','1d_view','7d_view','28d_view'].includes(w)))fail();
  if(e.click_window_days!==null||e.view_window_days!==null||e.report_time_basis!=='unknown'||e.provenance!=='provider_default_unknown'||['click_window_days','view_window_days','report_time_basis','provenance','producer_contract'].some(k=>e[k]!==p.attribution[k]))fail();
  if(scope.platform!=='meta_ads'&&(r.action_report_time!==null||r.use_unified_attribution_setting!==null||r.action_attribution_windows.length))fail();
  if(scope.platform==='google_ads'){
    if(s.report_support!=='existing_google_contract'||s.value_unit!=='account_currency_major'||p.producer_contract!=='google.v24.campaign-day.selected-action.v1')fail();
  }else if(s.profile==='meta.website-purchase-count.campaign-day.v1'){
    if(s.report_support!=='documented_meta_count'||s.value_unit!=='unknown'||p.producer_contract!=='meta.v26.campaign-day.website-purchase-count.v1'||r.action_report_time!==null||r.use_unified_attribution_setting!==null||r.action_attribution_windows.length)fail();
  }else if(!['unverified','unsupported'].includes(s.report_support)||s.value_unit!=='unknown'||p.producer_contract!=='unverified.'+s.profile||p.capability!==(s.report_support==='unsupported'?'unsupported':'unknown'))fail();
  return s;
}
function provenance(pin){
  const p=pin.observation_provenance;if(p==null)return null;
  const attr=p.attribution,scope=pin.aggregate.scope,names={google_ads:'google_conversion_action',meta_ads:'meta_action_type',tiktok_ads:'tiktok_event'},families={google_ads:['conversions','all_conversions'],meta_ads:['actions'],tiktok_ads:['event_count']};
  if(!['inlet.selected-observation-provenance.v1','inlet.selected-observation-provenance.v2'].includes(p.schema_version)||p.event_namespace!==names[scope.platform]||!families[scope.platform].includes(p.metric_family)||!bounded(p.native_event_owner_id,128)||!bounded(p.native_event_id,128)||!bounded(p.api_version,16)||!digest(p.query_profile_digest)||!bounded(p.producer_contract,160)||!['supported','unsupported','unknown'].includes(p.capability))fail();
  if(scope.platform==='google_ads'){if(!/^customers\/[0-9]{10}\/conversionActions\/[0-9]{1,32}$/.test(p.native_event_id)||p.native_event_id.split('/')[1]!==p.native_event_owner_id)fail();}else if(!/^[A-Za-z0-9_.:-]{1,128}$/.test(p.native_event_id))fail();
  if(!attr||attr.producer_contract!==p.producer_contract||!['interaction','conversion','unknown'].includes(attr.report_time_basis)||!['observed_response','verified_request_contract','provider_default_unknown'].includes(attr.provenance))fail();
  for(const k of ['click_window_days','view_window_days'])if(attr[k]!==null&&(!Number.isSafeInteger(attr[k])||attr[k]<0||attr[k]>400))fail();
  if(attr.provenance==='provider_default_unknown'&&(attr.click_window_days!==null||attr.view_window_days!==null||attr.report_time_basis!=='unknown'))fail();
  for(const d of [p.requested_starts_on,p.requested_ends_on])if(typeof d!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(d)||!Number.isFinite(Date.parse(d))||new Date(d).toISOString().slice(0,10)!==d)fail();
  if(p.requested_starts_on<pin.aggregate.starts_on||p.requested_ends_on>pin.aggregate.ends_on||p.requested_starts_on>p.requested_ends_on||instant(p.started_at)>instant(p.completed_at))fail();
  const parts=new Intl.DateTimeFormat('en',{timeZone:scope.time_zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(p.started_at)),part=k=>parts.find(x=>x.type===k).value;
  if(p.requested_ends_on>=`${part('year')}-${part('month')}-${part('day')}`)fail();
  captureSettings(p,scope);
  return p;
}
function validatedPins(plan,accounts){
  const proof=plan.selected_reporting_proof,selectors=plan.inputs.selected_reporting,result=new Map();
  if(proof==null){if(selectors!=null)fail();return result;}
  if(!Array.isArray(proof.accounts)||proof.accounts.length!==accounts.size||!Array.isArray(selectors)||selectors.length>20)fail();
  const requested=new Map();
  for(const s of selectors){if(!positive(s.account_id)||!id(s.capture_id)||requested.has(s.account_id))fail();requested.set(s.account_id,s.capture_id);}
  for(const item of proof.accounts){
    const f=item.source_fence,key=accountKey(f?.account),a=accounts.get(key),pin=item.capture_pin;
    if(!a||result.has(key)||f.source_revision!==a.connection_version||!Number.isSafeInteger(f.privacy_revision)||f.privacy_revision<0||!digest(f.source_binding_digest))fail();
    result.set(key,item);
    if(!pin){if(requested.has(a.account_id))fail();continue;}
    const scope=pin.aggregate?.scope,head=item.selection_head;
    if(accountKey(pin.account)!==key||!sameFence(pin.source_fence,f)||!head||head.invalidated!==false||!id(pin.selection_id)||!digest(pin.selection_digest)||head.selection_id!==pin.selection_id||head.selection_digest!==pin.selection_digest||requested.get(a.account_id)!==pin.capture_id)fail();
    if(!scope||scope.workspace_id!==a.workspace_id||scope.account_id!==a.account_id||scope.connection_id!==a.connection_id||scope.platform!==a.platform||scope.privacy_revision!==f.privacy_revision||!positive(scope.generation)||!bounded(scope.native_account_id,128)||!bounded(scope.time_zone,64)||!/^[A-Z]{3}$/.test(scope.currency))fail();
    try{new Intl.DateTimeFormat('en',{timeZone:scope.time_zone});}catch{fail();}
    for(const date of [pin.aggregate.starts_on,pin.aggregate.ends_on])if(!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isFinite(Date.parse(date))||new Date(date).toISOString().slice(0,10)!==date)fail();
    if(pin.aggregate.starts_on>pin.aggregate.ends_on)fail();
    provenance(pin);
    const traffic=item.traffic_pin;
    if(traffic){const other=traffic.aggregate;if(!sameFence(traffic.source_fence,f)||traffic.campaign_map_digest!==pin.campaign_map_digest||!other||['completion_id','manifest_digest','starts_on','ends_on'].some(k=>other[k]!==pin.aggregate[k])||Object.keys(scope).some(k=>other.scope?.[k]!==scope[k]))fail();}
    requested.delete(a.account_id);
  }
  if(requested.size)fail();return result;
}
export function appendReportingComparability(host,plan,{freshness,now}){
  const input=plan.inputs,list=input.accounts;
  if(!Array.isArray(list)||!list.length||list.length>20)fail();
  const accounts=new Map();
  for(const a of list){const key=accountKey(a);if(a.workspace_id!==input.workspace_id||accounts.has(key)||[...accounts.values()].some(other=>other.account_id===a.account_id))fail();accounts.set(key,a);}
  const pins=validatedPins(plan,accounts),evidence=new Map();
  const captures=[...pins.values()].map(p=>p.capture_pin).filter(Boolean),hasSettings=captures.some(p=>p.observation_provenance?.settings!=null);
  if((plan.schema_version==='inlet.plan-version.v3')!==hasSettings)fail();
  if(['inlet.plan-version.v2','inlet.plan-version.v3'].includes(plan.schema_version)&&(!captures.length||captures.some(p=>p.observation_provenance==null)))fail();
  for(const e of plan.evidence){
    if(!bounded(e.key,200)||evidence.has(e.key)||e.workspace_id!==input.workspace_id||(e.account&&!accounts.has(accountKey(e.account))))fail();
    evidence.set(e.key,e);
  }
  const doc=host.ownerDocument,section=doc.createElement('section');section.id='planning-reporting-comparability';
  const add=(parent,tag,value)=>{const n=doc.createElement(tag);n.textContent=value;parent.append(n);return n;};
  add(section,'h3','Reporting Comparability');
  add(section,'p','Review Accounts Separately. This version does not qualify cross-platform CPA rankings, event equivalence, unique-customer totals or causal results. Matching currencies or reporting dates alone does not make observations comparable.');
  add(section,'p',`Displayed Version: ${plan.version} · ${freshness.replaceAll('_',' ')}. This is document-level freshness, not verification that every account or attribution setting is current.`);
  add(section,'p','Attribution Windows: Click-through, view-through and report-time basis are shown only when retained from the original capture; unavailable values remain unknown. Event Business Meaning: Not Qualified Across Accounts. These unknowns block numeric comparison.');
  add(section,'p',`Requested Primary Period: ${period(input.reporting_window)}`);
  add(section,'p',input.comparison_window?`Requested Comparison Period: ${period(input.comparison_window)}`:'Comparison Period: Not Requested.');
  const currencies=new Set();
  for(const [key,a] of accounts){
    const accountSection=doc.createElement('section');accountSection.dataset.reportingAccount=String(a.account_id);
    add(accountSection,'h4',`${platforms[a.platform]} · Account ${a.account_id}`);
    const retained=pins.get(key),pin=retained?.capture_pin,rows=[...evidence.values()].filter(e=>e.kind==='reported_metrics'&&e.account&&accountKey(e.account)===key);
    add(accountSection,'p',pin?'Selected Capture Retained. It is a reference to original observations, not proof that all requested days or attribution settings are available.':'Selected Capture: Unavailable In This Version. No qualified selected event is inferred from platform totals, connection settings or labels.');
    if(pin){const scope=pin.aggregate.scope;currencies.add(scope.currency);add(accountSection,'p',`Recorded Currency: ${scope.currency} · Account Time Zone: ${scope.time_zone} · Advertiser ${scope.native_account_id}`);}
    else add(accountSection,'p','Recorded Selected-Report Currency And Time Zone: Unavailable. The Shopify goal currency and time zone are not substituted.');
    if(!rows.length)add(accountSection,'p','Selected/Traffic Reporting Evidence: Unavailable. Missing observations are not zero. Review the recorded explanations for this account’s exact gaps.');
    else add(accountSection,'p','Coverage requires review. Partial or unavailable evidence is not a complete-period total or zero; exact day counts, when retained, appear in the recorded explanation.');
    const originalMetadata=pin?provenance(pin):null;
    if(originalMetadata){
      const p=originalMetadata,at=p.attribution,days=v=>v===null?'Unavailable':`${v} Days`;
      add(accountSection,'p',`Recorded Selected Event: ${p.native_event_id} · Namespace ${p.event_namespace} · Owner ${p.native_event_owner_id} · Metric Family ${p.metric_family} · Capability ${p.capability}. Selection is not business equivalence or coverage proof.`);
      if(!p.settings&&a.platform!=='google_ads')add(accountSection,'p','Legacy Social Attribution: Effective settings are unverified. Historical request-contract flags are not proof of effective windows or reporting time.');
      else add(accountSection,'p',`Recorded Attribution: Click ${days(at.click_window_days)} · View ${days(at.view_window_days)} · Report Time ${at.report_time_basis} · Provenance ${at.provenance}. Original settings only; no cross-account comparability is granted.`);
      if(p.settings){const s=p.settings,r=s.requested;
        add(accountSection,'p',`Capture Profile: ${s.profile} · Report Support: ${s.report_support} · Count Meaning: ${s.count_meaning} · Value Unit: ${s.value_unit}. Profile support does not verify a live account.`);
        add(accountSection,'p',`Requested Settings: action_report_time=${r.action_report_time??'Not Sent'} · use_unified_attribution_setting=${r.use_unified_attribution_setting??'Not Sent'} · action_attribution_windows=${r.action_attribution_windows.join(', ')||'Not Sent'}. Requests are not effective settings.`);
        add(accountSection,'p','Effective Settings: Unknown. Click/View Windows And Report Time Are Unverified; Requested Values Are Not Substituted.');
        if(a.platform==='meta_ads')add(accountSection,'p','Meta ignores action_report_time and use_unified_attribution_setting under its current contract. Retired 7d_view/28d_view requests return no data, not zero.');
        if(s.profile==='meta.website-purchase-count.campaign-day.v1')add(accountSection,'p','Exact Website-Purchase Action Count Only. Counting Mode And Campaign Status Completeness Are Unverified. Missing Days Are Not Zero; Money Is Unsupported.');
        if(s.value_unit==='unknown')add(accountSection,'p','Monetary Value: Unavailable Until Units And Scaling Are Verified.');
      }else add(accountSection,'p','Requested Settings: Not Retained By This Historical Capture; Absence Is Not Inferred.');
    }else add(accountSection,'p','Typed Event And Attribution Metadata: Unavailable In This Version. Original explanations below remain unchanged; no metadata is reconstructed from their wording.');
    const details=doc.createElement('details');add(details,'summary','Review Source, Periods And Recorded Explanations');
    add(details,'p',`Source: ${platforms[a.platform]} · Account ${a.account_id} · Connection ${a.connection_id} · Original Revision ${a.connection_version}`);
    if(pin)add(details,'p',`Capture ${pin.capture_id} · Confirmed Choice Reference ${pin.selection_id} · Aggregate Acquisition Range ${pin.aggregate.starts_on} Through ${pin.aggregate.ends_on} (Inclusive Account-Local Dates). This range alone does not establish complete day coverage.`);
    if(originalMetadata){const p=originalMetadata;add(details,'p',`Original Selected Request: ${p.requested_starts_on} Through ${p.requested_ends_on} (Inclusive Account-Local Dates) · API ${p.api_version} · Producer ${p.producer_contract} · Query Profile ${p.query_profile_digest} · Read ${p.started_at} → ${p.completed_at}. Capture interval does not establish complete day coverage.`);}
    for(const e of rows){
      if(!['complete_in_declared_scope','partial','unavailable'].includes(e.coverage)||!Array.isArray(e.reasons)||e.reasons.length>30||e.reasons.some(r=>!bounded(r))||!bounded(e.metric_basis)||!bounded(e.declared_scope))fail();
      if(['inlet.selected-plan-window.v1','inlet.selected-traffic-window.v1'].includes(e.document_schema)&&(!pin||e.source_revision!==pin.source_fence.source_revision||e.source_binding_digest!==pin.source_fence.source_binding_digest||e.privacy_revision!==pin.source_fence.privacy_revision))fail();
      if(e.document_schema==='inlet.selected-traffic-window.v1'&&!retained?.traffic_pin)fail();
      const entry=doc.createElement('section'),kind=e.document_schema==='inlet.selected-plan-window.v1'?'Selected Event Observations':e.document_schema==='inlet.selected-traffic-window.v1'?'Reported Traffic':'Other Retained Reporting Evidence';
      const label=samePeriod(e.reporting_window,input.reporting_window)?'Primary':samePeriod(e.reporting_window,input.comparison_window)?'Comparison':'Other Retained';
      add(entry,'h5',`${label} · ${kind}`);
      add(entry,'p',e.reporting_window?period(e.reporting_window):'Reporting Period: Unavailable.');
      add(entry,'p',`Coverage: ${e.coverage.replaceAll('_',' ')} · ${e.declared_scope} · Basis: ${e.metric_basis}`);
      const started=instant(e.observation_started_at),observed=instant(e.observed_at),expiry=instant(e.expires_at);if(started>observed||observed>=expiry)fail();
      add(entry,'p',`Original Read: ${new Date(started).toISOString()} → ${new Date(observed).toISOString()}. Expires: ${new Date(expiry).toISOString()}${now>=expiry?' · Expired Evidence':''}.`);
      for(const reason of e.reasons)add(entry,'p',`Coverage/Qualification Reason: ${reason.replaceAll('_',' ')}`);
      add(entry,'p',`Evidence Reference: ${e.key} · Original Source Revision ${e.source_revision}`);details.append(entry);
    }
    for(const action of plan.actions){
      if(!action.target?.account||accountKey(action.target.account)!==key||!action.key.startsWith('review:'))continue;
      if(!bounded(action.rationale)||!Array.isArray(action.evidence_keys)||action.evidence_keys.length>400)fail();
      const references=action.evidence_keys.map(k=>{const e=evidence.get(k);if(!e||(e.kind==='reported_metrics'&&(!e.account||accountKey(e.account)!==key)))fail();return e;});
      const explanation=doc.createElement('section'),ref=action.target.provider_reference;
      add(explanation,'h5',`Recorded Measurement Explanation · ${action.target.display_name??'Name Unavailable'}${ref?` · ${action.target.kind} ${ref.entity_id}`:''}`);
      add(explanation,'p',action.rationale);
      add(explanation,'p',`Recorded Explanation: Preserved verbatim alongside any typed original metadata above. Its wording is not a verified cross-account event taxonomy. Reporting Evidence References: ${references.filter(e=>e.kind==='reported_metrics').map(e=>e.key).join(', ')||'Unavailable'}.`);
      details.append(explanation);
    }
    accountSection.append(details);section.append(accountSection);
  }
  if(currencies.size>1)add(section,'p',`Different Recorded Currencies: ${[...currencies].sort().join(', ')}. No currency conversion, aggregation or numeric comparison is performed.`);
  add(section,'h4','What Must Be Aligned Or Verified');
  const checks=doc.createElement('ol');
  for(const item of [
    'Verify each native event’s business meaning and metric family. A lead is not a purchase; matching names do not prove equivalence.',
    'Verify click-through and view-through attribution windows and report-time basis from original source evidence. Unknown settings remain unknown.',
    'Check account currencies, time zones, closed reporting periods and complete day coverage. Keep partial subtotals separate; absent data is not zero.',
    'Review fresh authorized source observations. If evidence changed or is missing, explicitly choose a supported reporting capture, revise plan inputs and generate a new version. A historical version is not refreshed by opening this review.',
    'Until these gaps are resolved, use the account-specific qualitative review. Do not rank incompatible cost-per-event figures, sum platform conversions as unique customers, or justify a budget transfer or causal sales claim from them.',
  ])add(checks,'li',item);
  section.append(checks);host.append(section);
}
