import {planningCapability} from './plan-capability.mjs';
import {parsePlanningMicros} from './plan-target-picker.mjs';
const mounted=new WeakMap(),digest=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const primitiveKeys=['schema_version','account_id','owner_selection_id','expected_observation_digest','expected_owner_facts_digest','scenario_key','currency','cadence','unit','requested_amount_micros'];
const amount=v=>Number.isSafeInteger(v)&&v>=0&&v<=1e15;
export const ownerAmount=v=>{if(!amount(v))throw Error('Daily amount unavailable.');return `${Math.floor(v/1e6)}.${String(v%1e6).padStart(6,'0')}`;};
const fail=message=>{throw Error(message);};
export function renderGoogleOwnerInputs(host,{capability,workspaceId,saved=null,context,discover,current}){
 mounted.get(host)?.clear();host.replaceChildren();host.hidden=true;
 const enabled=planningCapability(capability,workspaceId).ownerReview===true,token={};let alive=true,busy=false,generation=0,options=[],entries=[],snapshot=null;
 const doc=host.ownerDocument,node=(tag,value)=>{const n=doc.createElement(tag);if(value!==undefined)n.textContent=String(value);return n;};
 const check=()=>{if(!alive||mounted.get(host)!==handle)fail('Owner review choices changed.');current();};
 const status=node('p');status.dataset.role='owner-status';status.setAttribute('role','status');
 const rows=node('div'),choices=node('div');
 const button=(label,role,fn)=>{const n=node('button',label);n.type='button';n.dataset.role=role;n.onclick=async()=>{let issued=generation;try{check();if(busy)return;const pending=fn();issued=generation;await pending;}catch(error){if(alive&&mounted.get(host)===handle&&issued===generation){try{current();status.textContent=error.message;}catch{ /* Original session no longer owns this display. */ }}}};return n;};
 const currentContext=()=>{check();const c=structuredClone(context());if(!Array.isArray(c.catalogs)||!Array.isArray(c.scenarios)||!Array.isArray(c.exclusions)||!amount(c.totalCeilingMicros)||!/^[A-Z]{3}$/.test(c.currency))fail('Read current targets and complete your alternatives.');return c;};
 const stamp=c=>JSON.stringify(c);
 const key=o=>{const a=o.representative.account;return JSON.stringify([a.workspace_id,a.account_id,a.connection_id,a.platform,a.connection_version,o.representative.budget_owner_key]);};
 function coherent(option,c,account){
  if(option.account_id!==account.id||!digest(option.owner_selection_id)||!digest(option.expected_observation_digest)||!digest(option.expected_owner_facts_digest)||!amount(option.current_amount_micros)||option.currency!==c.currency||option.cadence!=='daily'||option.unit!=='micros'||option.advertising_writes_enabled!==false||option.spending_authority!=='none'||option.review_only!==true||option.economic_qualification!=='not_assessed'||!Array.isArray(option.affected_campaigns)||option.affected_campaigns.length<2||option.affected_campaigns.length>200||!Number.isFinite(Date.parse(option.expires_at))||Date.parse(option.expires_at)<=Date.now())fail('Owner observations could not be verified. Read targets again.');
  const catalog=c.catalogs.find(item=>item.account.id===account.id)?.catalog;
  const native=catalog?.native_observation,metadata=catalog?.metadata_observation;
  if(!native||!metadata||!Array.isArray(catalog.targets)||Date.parse(option.expires_at)!==Date.parse(catalog.expires_at))fail('Owner catalog binding could not be verified.');
  const rep=option.representative,seen=new Set();if(!rep?.account||rep.account.account_id!==account.id||rep.account.workspace_id!==workspaceId||rep.account.platform!=='google_ads'||!digest(rep.budget_owner_key)||JSON.stringify(rep)!==JSON.stringify(option.affected_campaigns[0]))fail('Owner membership could not be verified.');
  for(const observation of [native,metadata]){const a=rep.account;if(observation.workspace_id!==a.workspace_id||observation.account_id!==a.account_id||observation.connection_id!==a.connection_id||observation.connection_version!==a.connection_version||observation.platform!==a.platform)fail('Owner source generation differs from the original targets.');}
  for(const member of option.affected_campaigns){const target=catalog.targets.find(t=>t.canonical_entity_key===member.canonical_entity_key);if(!target||target.selection_key!==member.selection_key||target.budget_owner_key!==member.budget_owner_key||target.entity.kind!==member.kind||target.entity.name!==member.display_name||JSON.stringify(target.entity.reference)!==JSON.stringify(member.provider_reference))fail('Owner member differs from the original target catalog.');if(JSON.stringify(member.account)!==JSON.stringify(rep.account)||member.kind!=='campaign'||member.budget_owner_key!==rep.budget_owner_key||!digest(member.canonical_entity_key)||seen.has(member.canonical_entity_key))fail('Owner membership could not be verified.');seen.add(member.canonical_entity_key);}
 }
 function validScenario(o,c,scenarioKey){
  const scenario=c.scenarios.find(s=>s.key===scenarioKey);if(!scenario)fail('Choose a complete customer alternative.');
  const memberKeys=new Set(o.affected_campaigns.map(m=>m.canonical_entity_key));
  const allocations=scenario.allocations.filter(a=>a.target.account_id===o.account_id&&memberKeys.has(a.target.canonical_entity_key));
  if(allocations.length!==1)fail('Choose an alternative with exactly one allocation to an affected campaign.');
  const catalog=c.catalogs.find(item=>item.account.id===o.account_id)?.catalog;
  if(!catalog)fail('Read the original account targets again.');
  const memberIds=new Set(o.affected_campaigns.map(m=>m.provider_reference.entity_id));
  for(const e of c.exclusions){const target=catalog.targets.find(t=>t.canonical_entity_key===e.canonical_entity_key);if(target&&(memberKeys.has(e.canonical_entity_key)||memberIds.has(target.entity.reference.parent_campaign_id)))fail('An affected campaign or child is excluded. Review your target choices.');}
  return scenario;
 }
 function renderEntries(){
  rows.replaceChildren();entries.forEach((entry,index)=>{const row=node('section');row.dataset.index=String(index);const p=entry.intent;
   row.append(node('p',`${entry.ready?'Included Review':'Saved Or Changed Review — Reselect Before Saving'} · Customer Alternative ${p.scenario_key} · Requested Daily Hypothesis ${p.currency} ${ownerAmount(p.requested_amount_micros)} Per Day`));
   if(entry.historical)row.append(node('p',`Historical Observed Daily Setting: ${p.currency} ${ownerAmount(entry.historical.observed_amount_micros)} Per Day`));
   if(entry.option){const members=node('ul');members.dataset.role='owner-members';entry.option.affected_campaigns.forEach(m=>members.append(node('li',m.display_name??'Campaign Name Unavailable')));row.append(members);}
   row.append(button('Remove This Review','owner-remove',()=>{entries.splice(entries.indexOf(entry),1);renderEntries();}));rows.append(row);
  });setBusy(busy);
 }
 function renderOptions(c){
  choices.replaceChildren();if(!options.length)return;
  const label=node('label','Shared Google Budget '),select=node('select');select.dataset.role='owner-option';const empty=node('option','Choose A Shared Budget');empty.value='';select.append(empty);
  options.forEach((o,index)=>{const opt=node('option',o.affected_campaigns.map(m=>m.display_name??'Campaign Name Unavailable').join(' · '));opt.value=String(index);select.append(opt);});label.append(select);choices.append(label);
  const detail=node('div');choices.append(detail);
  select.onchange=()=>{detail.replaceChildren();if(busy)return;const o=options[Number(select.value)];if(select.value===''||!o)return;
   detail.append(node('p',`Observed Daily Setting: ${o.currency} ${ownerAmount(o.current_amount_micros)} Per Day`));
   const members=node('ul');members.dataset.role='owner-members';o.affected_campaigns.forEach(m=>members.append(node('li',m.display_name??'Campaign Name Unavailable')));detail.append(members);
   const alternative=node('select');alternative.dataset.role='owner-scenario';const blank=node('option','Choose A Customer Alternative');blank.value='';alternative.append(blank);c.scenarios.forEach(s=>{const n=node('option',s.title);n.value=s.key;alternative.append(n);});const al=node('label','Customer Alternative ');al.append(alternative);detail.append(al);
   const requested=node('input');requested.type='text';requested.inputMode='decimal';requested.maxLength=23;requested.dataset.role='owner-requested';const rl=node('label',`Requested Daily Hypothesis (${o.currency}) `);rl.append(requested);detail.append(rl);
   detail.append(button('Include This Review','owner-include',()=>{const fresh=currentContext();if(stamp(fresh)!==snapshot||Date.parse(o.expires_at)<=Date.now())fail('Owner choices expired or changed. Read targets and reselect.');validScenario(o,fresh,alternative.value);const value=parsePlanningMicros(requested.value);if(value>BigInt(o.current_amount_micros)||(fresh.totalCeilingMicros===0&&value!==0n))fail('The daily hypothesis cannot exceed the observed setting; a zero ceiling requires zero.');
    if(entries.some(e=>!e.ready))fail('Explicitly remove historical reviews before including new observations.');if(entries.length>=20)fail('Include at most twenty owner reviews.');if(entries.some(e=>e.option?key(e.option)===key(o):e.intent.account_id===o.account_id&&e.intent.owner_selection_id===o.owner_selection_id))fail('Remove the earlier review for this owner before replacing it.');
    const intent={schema_version:'inlet.google-daily-budget-intent.v1',account_id:o.account_id,owner_selection_id:o.owner_selection_id,expected_observation_digest:o.expected_observation_digest,expected_owner_facts_digest:o.expected_owner_facts_digest,scenario_key:alternative.value,currency:o.currency,cadence:o.cadence,unit:o.unit,requested_amount_micros:Number(value)};
    entries.push({intent,option:structuredClone(o),ready:true});renderEntries();status.textContent='Review included. No advertising change will be applied.';
   }));setBusy(busy);
  };
 }
 const discovery=button('Review Shared Google Budget','owner-discover',async()=>{
  const c=currentContext(),version=++generation,signature=stamp(c);options=[];choices.replaceChildren();snapshot=null;
  const collected=[];let unavailable=false;
  for(const {account,catalog} of c.catalogs.filter(item=>item.account.platform==='google_ads')){
   const result=await discover({account_id:account.id,catalog_composite_digest:catalog.composite_digest,reporting_window:c.reportingWindow});
   check();if(version!==generation||stamp(currentContext())!==signature)return;
   if(result.account_id!==account.id||result.advertising_writes_enabled!==false||result.spending_authority!=='none'||!Array.isArray(result.owners)||result.owners.length>20)fail('Owner discovery could not be verified.');
   if(result.status==='unavailable'){if(result.owners.length||result.reason!=='google_budget_owner_unavailable')fail('Owner discovery could not be verified.');unavailable=true;continue;}
   if(result.status!=='available'||result.reason!==null||!result.owners.length)fail('Owner discovery could not be verified.');
   for(const o of result.owners){coherent(o,c,account);if(collected.some(old=>key(old)===key(o)))fail('Duplicate owner observations.');collected.push(o);}
  }
  options=collected;snapshot=signature;renderOptions(c);status.textContent=unavailable?'Shared Budget Review Unavailable. Read fresh targets and review the full affected campaigns.':(options.length?'Choose a shared budget and customer alternative.':'Read targets for an included Google Ads account first.');
 });
 function setBusy(value){busy=Boolean(value);for(const n of host.querySelectorAll('button,input,select'))n.disabled=busy;}
 const handle=Object.freeze({
  readIntents(){check();if(!enabled)return undefined;if(entries.length){const c=currentContext();if(stamp(c)!==snapshot)fail('Owner context changed. Reselect or remove the reviews.');for(const e of entries){if(!e.ready||!e.option||Date.parse(e.option.expires_at)<=Date.now())fail('Saved owner reviews require explicit removal and current reselection.');validScenario(e.option,c,e.intent.scenario_key);}}return entries.map(e=>structuredClone(e.intent));},
  setBusy,
  invalidateChoices(){if(!alive)return;generation++;options=[];snapshot=null;entries.forEach(e=>e.ready=false);choices.replaceChildren();renderEntries();status.textContent='Owner choices changed. Read current targets and explicitly reselect or remove reviews.';},
  clear(){if(!alive)return;alive=false;generation++;entries=[];options=[];if(mounted.get(host)===handle){mounted.delete(host);host.replaceChildren();host.hidden=true;}}
 });mounted.set(host,handle);
 if(!enabled){if(saved!==null&&saved!==undefined)fail('This saved plan requires owner review availability.');return handle;}
 if(saved!==null){if(!Array.isArray(saved)||saved.length>20)fail('Saved owner reviews could not be verified.');entries=saved.map(p=>{if(!amount(p.requested_amount_micros)||!amount(p.observed_amount_micros)||!digest(p.owner_key)||!digest(p.owner_selection_id))fail('Saved owner review could not be verified.');return{intent:Object.fromEntries(primitiveKeys.map(k=>[k,structuredClone(p[k])])),historical:structuredClone(p),ready:false,option:null};});}
 host.append(node('h3','Shared Google Daily Settings'),node('p','Daily Settings And Plan Allocations Are Different. This is a request to review an observed Google setting. A daily setting does not guarantee total spending within your confirmed plan ceiling. Inlet will not apply this change.'),discovery,status,choices,rows);host.hidden=false;renderEntries();return handle;
}
