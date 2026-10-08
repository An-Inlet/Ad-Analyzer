import {minuteValue,reportingPeriods} from './plan-periods.mjs';
import {clearPlanSalesProgress,renderPlanSalesProgress} from './plan-progress.mjs';
import {clearPlanDocument,renderPlanDocument} from './plan-document.mjs';
import {renderPlanComparison} from './plan-comparison.mjs';
const clearPlanComparison=host=>{host.replaceChildren();host.hidden=true;};
import {clearPlanScenarios,renderPlanScenarios} from './plan-scenarios.mjs';
import {clearPlanTargetPicker,renderPlanTargetPicker} from './plan-target-picker.mjs';
import {clearPlanEvents,renderPlanEvents} from './plan-events.mjs';
const $=id=>document.getElementById('planning-'+id),base='/api/customer/v1';
const platforms={google_ads:'Google Ads',meta_ads:'Meta Ads',tiktok_ads:'TikTok Ads'};
const id=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
const positive=value=>Number.isSafeInteger(value)&&value>0;
const noAuthority=value=>value?.advertising_writes_enabled===false&&value.spending_authority==='none';
const text=(tag,value)=>{const node=document.createElement(tag);node.textContent=String(value);return node;};
const say=value=>$('message').textContent=value;
let epoch=0,busy=false,operation=null,user=null,workspaces=[],wid='',role='',planId='',read=null;
let listCursor=null,versionCursor=null,eventCursor=null,eventSequence=0,displayCookies=null,expiryTimer=null;
let goals=[],accounts=[],editing=false,pending=null,currentView=false,eventItems=[],editWindow=null,editComparison=null,editExpected=null;
let scenarioHandle=null,targetPickers=[],targetTimer=null,targetScope=null,requiresReselection=false,targetReadRequired=false;
class Stale extends Error{}
function clearTargets(){clearPlanScenarios($('scenarios'));scenarioHandle=null;if(targetTimer!==null)clearTimeout(targetTimer);targetTimer=null;for(const item of targetPickers)clearPlanTargetPicker(item.host);targetPickers=[];targetScope=null;$('targets').replaceChildren();}
function comparisonControls(){const enabled=$('comparison-enabled').checked;$('comparison-fields').hidden=!enabled;for(const name of ['comparison-start','comparison-end']){$(name).required=enabled;$(name).disabled=busy||!enabled;}}
function changedTargetScope(){clearTargets();$('target-status').textContent='Goal, account or reporting choices changed. Read targets again before selecting exclusions or allocations.';}

const root=()=>`/workspaces/${encodeURIComponent(wid)}/planning/plans`;
const selected=()=>`${root()}/${planId}`;
function options(host,values,label,value){const empty=text('option','Choose…');empty.value='';host.replaceChildren(empty,...values.map(item=>{const option=text('option',label(item));option.value=String(value(item));return option;}));}
function clearDocument(){if(expiryTimer!==null)clearTimeout(expiryTimer);expiryTimer=null;clearPlanDocument($('document'));clearPlanComparison($('comparison'));clearPlanSalesProgress($('progress'));$('progress-read').hidden=true;}
function clearPlan(){clearDocument();clearPlanEvents($('events'));read=null;planId='';eventItems=[];$('review').hidden=true;$('review-form').reset();options($('action'),[],v=>v,v=>v);options($('prior'),[],v=>v,v=>v);$('head').textContent='';$('plan-title').textContent='Selected Plan';versionCursor=eventCursor=null;eventSequence=0;$('current').hidden=$('events-controls').hidden=true;options($('version'),[],v=>v,v=>v);}
function clearEditor(){clearTargets();requiresReselection=false;targetReadRequired=false;$('target-status').textContent='';$('editor').hidden=true;$('form').reset();goals=[];accounts=[];editing=false;editWindow=null;editComparison=null;editExpected=null;comparisonControls();options($('goal'),[],v=>v,v=>v);$('accounts').replaceChildren();$('goal-summary').textContent='';}
function clearSessionChoices(){workspaces=[];$('plans').replaceChildren();options($('workspace'),[],v=>v,v=>v);$('new').hidden=true;}
function invalidate(){epoch++;busy=false;clearPlan();clearEditor();enable();}
function enable(){
  for(const node of document.querySelectorAll('button,input,select,textarea'))node.disabled=busy;
  $('refresh').disabled=false;$('workspace').disabled=false;comparisonControls();
  for(const name of ['save','generate','edit','new','record'])$(name).disabled=busy||pending!==null;
  $('generate').disabled=busy||pending!==null||!$('editor').hidden;
  $('generate').hidden=role!=='owner'||!read||!currentView;
  $('edit').hidden=role!=='owner'||!read;
  $('progress-read').hidden=!read?.document||$('document').hidden;
  $('export').hidden=!read?.document;$('compare').hidden=!read?.document||read.version<2;
  $('list-next').hidden=listCursor===null;$('versions-next').hidden=versionCursor===null;
  $('events-next').hidden=eventCursor===null;
  $('pending').hidden=pending===null||pending.user!==user;
  $('pending-reference').textContent=pending&&pending.user===user?`Request reference: ${pending.key}`:'';
  $('recover').disabled=busy||!pending||pending.user!==user||pending.workspace!==wid;
  $('retry').hidden=!pending?.absent||pending.user!==user||pending.workspace!==wid;$('retry').disabled=busy;
  const withdrawing=$('record-type').value==='retracted';
  $('record').disabled=busy||pending!==null||!$('editor').hidden||!read?.document||!$('confirm-review').checked||(withdrawing?!$('prior').value:(!currentView||read.freshness!=='current'||Date.now()>=Date.parse(read.document.valid_until)));
  $('review').hidden=!$('editor').hidden||role!=='owner'||!read?.document;
}
function check(turn){if(turn!==epoch)throw new Stale();if(!operation||operation.turn!==turn||document.cookie!==operation.cookies)throw Object.assign(Error('Your session changed. Refresh your session before continuing.'),{status:401});}
async function api(path,turn,method='GET',body){
  check(turn);const headers={Accept:'application/json'},cookies=operation.cookies;
  if(method!=='GET'){
    const csrf=cookies.split(';').map(v=>v.trim()).find(v=>v.startsWith('__Host-inlet_csrf='))?.slice('__Host-inlet_csrf='.length);
    if(!/^[A-Za-z0-9_-]{43}$/.test(csrf||''))throw Object.assign(Error('Sign in from Your Workspace.'),{status:401});
    headers['X-CSRF-Token']=csrf;if(body!==undefined)headers['Content-Type']='application/json';
  }
  let response;
  try{response=await fetch(base+path,{method,headers,credentials:'same-origin',cache:'no-store',redirect:'error',body:body===undefined?undefined:JSON.stringify(body)});}
  catch{check(turn);throw Error('The response was not received. Check the previous request result if a save was in progress.');}
  if(path==='/session'&&method==='DELETE'){if(turn!==epoch)throw new Stale();}
  else check(turn);
  let result;try{result=response.status===204?null:await response.json();}catch{check(turn);throw Error('The response could not be read. Check the previous request result if a save was in progress.');}
  if(path!=='/session'||method!=='DELETE')check(turn);
  if(!response.ok)throw Object.assign(Error(({401:'Your session ended. Sign in from Your Workspace.',402:'Workspace access is unavailable. Check billing.',403:'This action requires current owner access.',404:'The selected item or recorded result is unavailable.',409:'The plan, source or selected snapshot changed. Read the current plan and review your inputs.',422:'Review the entered values and reporting period.',503:'Planning is temporarily unavailable.'})[response.status]||'The request could not be completed.'),{status:response.status});
  return result;
}
async function session(turn){const result=await api('/session',turn);if(user!==null&&result.user_id!==user)throw Object.assign(Error('Your signed-in customer changed. Refresh your session.'),{status:401});return result;}
async function guarded(action,authenticate=true){
  if(busy)return;if(authenticate&&displayCookies!==null&&document.cookie!==displayCookies){invalidate();clearSessionChoices();$('selection').hidden=true;say('Your session changed. Refresh your session before continuing.');return;}const turn=++epoch;operation={turn,cookies:document.cookie};busy=true;enable();
  try{if(authenticate)await session(turn);await action(turn);check(turn);displayCookies=operation.cookies;}
  catch(error){if(!(error instanceof Stale)){clearDocument();clearPlanEvents($('events'));if([401,403,404].includes(error.status)){invalidate();if(error.status===401){clearSessionChoices();$('selection').hidden=true;}}say(error.message||'Planning is unavailable.');}}
  finally{if(turn===epoch){busy=false;enable();}}
}
async function loadSession(turn){
  clearPlan();clearEditor();wid='';role='';user=null;listCursor=null;$('plans').replaceChildren();$('selection').hidden=true;
  const current=await api('/session',turn);user=current.user_id;if(pending&&pending.user!==user)pending=null;
  workspaces=await api('/workspaces',turn);if(!Array.isArray(workspaces)||workspaces.some(w=>!positive(w.id)||typeof w.name!=='string'))throw Error('The workspace list could not be verified.');
  options($('workspace'),workspaces,w=>w.name,w=>w.id);$('selection').hidden=false;$('logout').hidden=false;say('Choose a workspace to review its plans.');
}
async function listPlans(turn,cursor=null){
  const page=await api(root()+`?limit=20${cursor===null?'':'&cursor='+encodeURIComponent(cursor)}`,turn);
  if(!Array.isArray(page.items)||page.items.length>20||page.items.some(p=>!id(p.plan_id)||!noAuthority(p)))throw Error('The plan list could not be verified.');
  $('plans').replaceChildren(...page.items.map(item=>{const li=document.createElement('li'),button=text('button',`Plan ${item.plan_id.slice(0,8)} · Version ${item.version} · Input Revision ${item.input_revision}`);button.onclick=()=>{invalidate();planId=item.plan_id;guarded(async t=>{await readPlan(t);await versions(t);});};li.append(button);return li;}));
  listCursor=page.next_cursor;say(page.items.length?'Choose a saved plan or prepare a new plan.':'No plans were returned on this page.');
}
function validateRead(value,version=null){
  if(!noAuthority(value)||value.plan_id!==planId||value.inputs?.workspace_id!==Number(wid)||value.inputs?.plan_id!==planId||value.inputs.revision!==value.input_revision||!Number.isSafeInteger(value.version)||value.version<0||(version!==null&&value.version!==version)||(value.document!==null&&(value.document.version!==value.version||value.document.inputs?.plan_id!==planId)))throw Error('The plan response did not match the requested scope and version.');
}
function showRead(value){
  validateRead(value);clearDocument();read=value;$('current').hidden=false;$('events-controls').hidden=false;
  $('plan-title').textContent=`Plan ${planId.slice(0,8)}`;$('head').textContent=`Input Revision ${value.input_revision} · Displayed Version ${value.version} · Customer History Sequence ${value.event_sequence}`;
  $('confirm-review').checked=false;options($('action'),value.document?.actions??[],a=>a.title,a=>a.key);reviewChoices();
  if(value.document){
    const result=renderPlanDocument($('document'),value.document,{workspaceId:Number(wid),planId,freshness:value.freshness,reasons:value.reasons});
    if(result.freshness==='current')expiryTimer=setTimeout(()=>{if(read===value){clearPlanComparison($('comparison'));renderPlanDocument($('document'),value.document,{workspaceId:Number(wid),planId,freshness:'expired',reasons:['The original evidence deadline elapsed. Read the current plan before making a new decision.']});enable();}},Math.min(2147483647,Math.max(0,Date.parse(value.document.valid_until)-Date.now())));
  }else say('Inputs are saved. Generate a version when ready; no advertising data has been read for generation yet.');
}
async function readPlan(turn,version=null){
  const value=await api(selected()+(version===null?'':`/versions/${version}`),turn);await session(turn);check(turn);validateRead(value,version);currentView=version===null;showRead(value);$('version').value=String(value.version);
}
async function versions(turn,cursor=null){
  const page=await api(selected()+`/versions?limit=20${cursor===null?'':'&cursor='+encodeURIComponent(cursor)}`,turn);
  if(!noAuthority(page)||!Array.isArray(page.items)||page.items.length>20||page.items.some(item=>item.plan_id!==planId||!positive(item.version)))throw Error('The version history could not be verified.');
  options($('version'),page.items,item=>`Version ${item.version}`,item=>item.version);$('version').value=read?String(read.version):'';versionCursor=page.next_cursor;
}
async function events(turn,cursor=null){
  const page=await api(selected()+`/events?limit=20${cursor===null?'':'&cursor='+encodeURIComponent(cursor)}`,turn);await session(turn);check(turn);
  const result=renderPlanEvents($('events'),page,{workspaceId:Number(wid),planId,afterSequence:cursor===null?0:eventSequence});eventCursor=result.nextCursor;eventSequence=result.lastSequence;eventItems=page.items;reviewChoices();
}
function goalSummary(){const goal=goals.find(g=>g.id===$('goal').value);$('goal-summary').textContent=goal?`Confirmed Goal Revision ${goal.revision} · ${goal.definition.target_window.currency} ${(goal.definition.budget_micros/1e6).toFixed(2)} Budget Ceiling · ${goal.definition.aggressiveness} Aggressiveness. This does not increase spending permission.`:'';}
async function editor(turn,isEdit=false){
  clearEditor();editing=isEdit;
  const allGoals=await api(`/workspaces/${wid}/goals`,turn),catalog=await api(`/workspaces/${wid}/planning/accounts`,turn);
  if(!Array.isArray(allGoals)||catalog.complete!==true||!Array.isArray(catalog.accounts))throw Error('The goal and account choices could not be verified.');
  goals=allGoals.filter(g=>g.workspace_id===Number(wid)&&g.confirmation_recorded===true&&g.confirmed_at!==null&&g.definition);accounts=catalog.accounts;
  options($('goal'),goals,g=>`${g.definition.milestone??'Confirmed Goal'} · Revision ${g.revision}`,g=>g.id);
  $('accounts').replaceChildren(...accounts.map(a=>{const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=String(a.id);input.onchange=changedTargetScope;label.append(input,document.createTextNode(`${a.name} · ${platforms[a.platform]??'Unsupported'}`));return label;}));
  if(isEdit){
    const input=read.inputs;editExpected={expected_input_revision:read.input_revision,expected_version:read.version};
    requiresReselection=Boolean(input.excluded_entity_keys.length||input.fixed_allocations.length||input.scenario_intents.length);
    if(requiresReselection)$('target-status').textContent='This revision contains saved target choices. Read targets and explicitly select the choices for the new revision, then confirm replacement below. Old choices are not copied to new observations.';
    $('goal').value=input.goal.goal_id;for(const node of $('accounts').querySelectorAll('input'))node.checked=input.accounts.some(a=>String(a.account_id)===node.value);
    $('milestone').value=input.milestone;$('product').value=input.product_offer??'';$('constraints').value=input.constraints.join('\n');$('assumptions').value=input.assumptions.map(a=>a.statement).join('\n');
    $('start').value=minuteValue(input.reporting_window.starts_at);$('end').value=minuteValue(input.reporting_window.ends_at_exclusive);$('creative').value=input.maximum_creative_assets===null?'':String(input.maximum_creative_assets);editWindow=input.reporting_window;editComparison=input.comparison_window;$('comparison-enabled').checked=editComparison!==null;if(editComparison){$('comparison-start').value=minuteValue(editComparison.starts_at);$('comparison-end').value=minuteValue(editComparison.ends_at_exclusive);}comparisonControls();
  }
  $('editor-title').textContent=isEdit?'Edit Plan Inputs':'Prepare A New Plan';goalSummary();$('editor').hidden=false;say('Review the goal, accounts, milestone and reporting period before saving.');
}
function lines(value){const values=value.split('\n').map(v=>v.trim()).filter(Boolean);if(values.length>30||values.some(v=>v.length>2000))throw Error('Use at most 30 entries, each no longer than 2,000 characters.');return values;}
function iso(value){if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value))throw Error('Enter reporting times in UTC.');const d=new Date(value+':00Z');if(!Number.isFinite(d.getTime())||d.toISOString().slice(0,16)!==value)throw Error('Enter valid reporting times.');return d.toISOString();}
function inputs(){
  const goal=goals.find(g=>g.id===$('goal').value);if(!goal)throw Error('Choose a confirmed goal.');
  const account_ids=[...$('accounts').querySelectorAll('input:checked')].map(n=>Number(n.value));if(!account_ids.length||account_ids.length>20)throw Error('Choose between one and twenty accounts.');
  const periods=reportingPeriods({start:$('start').value,end:$('end').value,comparisonEnabled:$('comparison-enabled').checked,comparisonStart:$('comparison-start').value,comparisonEnd:$('comparison-end').value,savedPrimary:editWindow,savedComparison:editComparison});const{starts_at,ends_at_exclusive}=periods.reporting_window;
  const maximum_creative_assets=$('creative').value===''?null:Number($('creative').value);if(maximum_creative_assets!==null&&(!Number.isSafeInteger(maximum_creative_assets)||maximum_creative_assets<0||maximum_creative_assets>30))throw Error('Choose zero to thirty creative concepts.');
  if(targetReadRequired&&!targetPickers.length)throw Error('Read targets again before saving. Earlier target choices were invalidated.');
  let exclusions=[],fixed_allocations=[];const scenario_intents=scenarioHandle?.readIntent()??[];
  if(targetScope!==null&&targetScope!==JSON.stringify({goal:goal.id,revision:goal.revision,account_ids,starts_at,ends_at_exclusive}))throw Error('Your target scope changed. Read targets again.');
  for(const item of targetPickers){const value=item.handle.readIntent();exclusions.push(...value.exclusions);fixed_allocations.push(...value.fixed_allocations);}
  if(requiresReselection&&(!targetPickers.length||!$('replace-targets').checked))throw Error('Read targets and explicitly confirm your replacement target choices for this revision.');
  if(exclusions.length>100||fixed_allocations.length>100||fixed_allocations.reduce((sum,a)=>sum+BigInt(a.amount_micros),0n)>BigInt(goal.definition.budget_micros))throw Error('Keep at most 100 exclusions and allocations, within the confirmed total budget ceiling.');
  for(const scenario of scenario_intents){if(scenario.allocations.some(a=>exclusions.some(e=>e.canonical_entity_key===a.target.canonical_entity_key))||fixed_allocations.some(f=>!scenario.allocations.some(a=>a.target.canonical_entity_key===f.target.canonical_entity_key&&a.amount_micros===f.amount_micros)))throw Error('Each alternative must preserve every fixed allocation and omit excluded targets.');}
  return{goal_id:goal.id,goal_revision:goal.revision,account_ids,...periods,milestone:$('milestone').value.trim(),product_offer:$('product').value.trim()||null,constraints:lines($('constraints').value),assumptions:lines($('assumptions').value),exclusions,fixed_allocations,scenario_intents,maximum_creative_assets};
}
async function mutate(turn,operationName,path,body){
  if(pending)throw Error('Check the previous request result before another save.');
  const key=crypto.randomUUID().replaceAll('-','');pending={user,workspace:wid,operation:operationName,key,path,body:{...body,request_key:key},absent:false};enable();
  try{const result=await api(path,turn,'POST',{...body,request_key:key});const resultPlan=result.plan_id??result.event?.plan_id;if(!noAuthority(result)||!id(resultPlan)||(operationName!=='create'&&resultPlan!==planId))throw Error('The saved response could not be verified. Check the recorded result.');pending=null;return result;}
  catch(error){if(error.status&&error.status<500&&error.status!==401)pending=null;throw error;}
}
function reviewChoices(){
  const kind=$('record-type').value,manual=['customer_reports_applied','retracted'].includes(kind);
  const matching=eventItems.filter(row=>row.event.version===read?.version&&row.event.action_key===$('action').value&&(manual?Object.hasOwn(row.event,'assertion'):Object.hasOwn(row.event,'decision')));
  options($('prior'),matching,row=>`Event ${row.event_sequence} · ${row.event.assertion??row.event.decision}`,row=>row.event.event_id);
  $('prior').options[0].textContent=kind==='retracted'?'Choose The Report To Withdraw':'First Record — No Earlier Record Replaced';
  $('applied-label').hidden=kind!=='customer_reports_applied';$('applied').required=kind==='customer_reports_applied';$('confirm-review').checked=false;enable();
}
for(const name of ['action','record-type'])$(name).onchange=reviewChoices;
$('prior').onchange=()=>{$('confirm-review').checked=false;enable();};$('confirm-review').onchange=enable;
$('review-form').onsubmit=event=>{event.preventDefault();guarded(async turn=>{
  if(!$('editor').hidden||!read?.document||!$('confirm-review').checked)throw Error('Review the exact document and action first.');
  const action=read.document.actions.find(a=>a.key===$('action').value),kind=$('record-type').value,manual=['customer_reports_applied','retracted'].includes(kind);
  if(!action)throw Error('Choose the action you reviewed.');
  const body={expected_version:read.version,expected_event_sequence:read.event_sequence,document_digest:read.document_digest,action_key:action.key,action_digest:read.action_digests[action.key],supersedes_event_id:$('prior').value||null};
  if(manual)Object.assign(body,{assertion:kind,statement:$('statement').value.trim(),reported_applied_at:kind==='customer_reports_applied'?iso($('applied').value):null});
  else Object.assign(body,{decision:kind,reason:$('statement').value.trim()});
  const version=currentView?null:read.version;
  await mutate(turn,manual?'assert_applied':'decide',selected()+(manual?'/assertions':'/decisions'),body);
  $('review-form').reset();await readPlan(turn,version);await events(turn);say('Your customer record was saved. No advertising change was made.');
});};
$('refresh').onclick=()=>{invalidate();guarded(loadSession,false);};
$('workspace').onchange=()=>{invalidate();wid=$('workspace').value;role=workspaces.find(w=>String(w.id)===wid)?.role??'';$('new').hidden=role!=='owner';$('plans').replaceChildren();listCursor=null;if(wid)guarded(t=>listPlans(t));};
$('list-refresh').onclick=()=>guarded(t=>listPlans(t));$('list-next').onclick=()=>guarded(t=>listPlans(t,listCursor));
$('new').onclick=()=>{clearPlan();guarded(t=>editor(t));};$('cancel').onclick=()=>{clearEditor();enable();};$('goal').onchange=()=>{goalSummary();changedTargetScope();};
for(const name of ['start','end'])$(name).oninput=changedTargetScope;
$('comparison-enabled').onchange=comparisonControls;
$('targets-read').onclick=()=>guarded(async turn=>{
  clearTargets();
  // Validate the form scope without requiring the old revision replacement confirmation.
  const replacing=requiresReselection;let intent;try{requiresReselection=false;targetReadRequired=false;intent=inputs();}finally{requiresReselection=replacing;targetReadRequired=true;}
  const goal=goals.find(g=>g.id===intent.goal_id),period={starts_at:intent.reporting_window.starts_at,ends_at:intent.reporting_window.ends_at_exclusive};
  try{for(const accountId of intent.account_ids){
    const account=accounts.find(a=>a.id===accountId),catalog=await api(`/workspaces/${wid}/planning/target-catalog-v2`,turn,'POST',{account_id:accountId,...period});
    await session(turn);check(turn);const host=document.createElement('section');$('targets').append(host);
    const handle=renderPlanTargetPicker(host,catalog,{workspaceId:Number(wid),account,period,currency:goal.definition.target_window.currency,totalCeilingMicros:goal.definition.budget_micros},()=>{$('replace-targets').checked=false;});
    targetPickers.push({host,handle,catalog,account});
  }
  for(const item of targetPickers)item.handle.readIntent();
  targetScope=JSON.stringify({goal:goal.id,revision:goal.revision,account_ids:intent.account_ids,starts_at:period.starts_at,ends_at_exclusive:period.ends_at});
  $('replace-targets').checked=false;$('target-status').textContent='Choose exclusions or fixed planning allocations below. These are customer budget hypotheses and never change advertising.';
  const expires=Math.min(...targetPickers.map(item=>Date.parse(item.handle.expiresAt)));
  scenarioHandle=renderPlanScenarios($('scenarios'),{currency:goal.definition.target_window.currency,totalCeilingMicros:goal.definition.budget_micros,expiresAt:new Date(expires).toISOString(),targets:targetPickers.flatMap(item=>item.catalog.targets.map(target=>({selector:{account_id:item.account.id,canonical_entity_key:target.canonical_entity_key,selection_key:target.selection_key},label:`${item.account.name} · ${target.entity.name??'Name Unavailable'} · ${target.entity.kind} ${target.entity.reference.entity_id}`})))},()=>{$('replace-targets').checked=false;});
  targetTimer=setTimeout(()=>{clearTargets();$('target-status').textContent='The target observations expired. Read again and explicitly reselect your choices.';},Math.min(2147483647,Math.max(0,expires-Date.now())));
  }catch(error){clearTargets();throw error;}
});
$('edit').onclick=()=>guarded(async t=>{await readPlan(t);await editor(t,true);});
$('form').onsubmit=event=>{event.preventDefault();guarded(async turn=>{const intent=inputs(),result=await mutate(turn,editing?'revise':'create',editing?selected()+'/inputs':root(),{inputs:intent,...(editing?editExpected:{})});if(!id(result.plan_id)||!noAuthority(result))throw Error('The saved result could not be verified.');planId=result.plan_id;clearEditor();await readPlan(turn);await versions(turn);say('Plan inputs saved. Generate a version when ready.');});};
$('read').onclick=()=>guarded(async t=>{await readPlan(t);await versions(t);});
$('generate').onclick=()=>guarded(async turn=>{if(!read||!$('editor').hidden)throw Error('Save or cancel edited inputs before generating.');const result=await mutate(turn,'generate',selected()+'/generate',{expected_input_revision:read.input_revision,expected_version:read.version});if(!noAuthority(result)||result.plan_id!==planId)throw Error('The generation result could not be verified.');await readPlan(turn);await versions(turn);say('A new immutable plan version is ready for review.');});
$('version').onchange=()=>{const version=Number($('version').value);clearDocument();if(positive(version))guarded(t=>readPlan(t,version));};
$('versions-next').onclick=()=>guarded(t=>versions(t,versionCursor));
$('events-refresh').onclick=()=>guarded(t=>events(t));$('events-next').onclick=()=>guarded(t=>events(t,eventCursor));
$('compare').onclick=()=>guarded(async turn=>{const version=read.version,old=await api(selected()+`/versions/${version-1}`,turn),value=await api(selected()+`/comparisons/${version-1}/${version}`,turn);await session(turn);check(turn);renderPlanComparison($('comparison'),value,{previous_version:version-1,current_version:version,previous_digest:old.document_digest,current_digest:read.document_digest});});
$('export').onclick=()=>guarded(async turn=>{const version=read.version,value=await api(selected()+`/export?version=${version}`,turn);await session(turn);check(turn);validateRead(value,version);const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=`inlet-plan-${planId}-version-${version}-artifact.json`;link.click();setTimeout(()=>URL.revokeObjectURL(url),0);say('Downloaded the selected version artifact. Customer event history is separate.');});
async function recovered(turn,value){const resultPlan=value.plan_id??value.event?.plan_id;if(!noAuthority(value)||!id(resultPlan))throw Error('The recorded result could not be verified.');pending=null;planId=resultPlan;clearEditor();await readPlan(turn);await versions(turn);say('The earlier request completed. Its saved plan is displayed.');}
$('recover').onclick=()=>guarded(async turn=>{
  if(!pending||pending.user!==user||pending.workspace!==wid)throw Error('Choose the original customer and workspace to check this request.');
  const saved=pending;let value;
  try{value=await api(root()+`/requests/${saved.operation}/${saved.key}`,turn);}
  catch(error){if(error.status===404){saved.absent=true;say('No recorded result was found. The earlier request may still finish. You may explicitly retry this exact request with the same reference.');return;}throw error;}
  await recovered(turn,value);
});
$('retry').onclick=()=>guarded(async turn=>{
  if(!pending?.absent||pending.user!==user||pending.workspace!==wid)throw Error('Check the original request result before retrying.');
  const saved=pending;saved.absent=false;const value=await api(saved.path,turn,'POST',saved.body);await recovered(turn,value);
});
$('logout').onclick=()=>{invalidate();guarded(async turn=>{await api('/session',turn,'DELETE');invalidate();user=null;wid='';role='';clearSessionChoices();$('selection').hidden=$('logout').hidden=true;say('Signed out.');},false);};
function changedSession(){if(displayCookies!==null&&document.cookie!==displayCookies){invalidate();clearSessionChoices();$('selection').hidden=true;say('Your session changed. Refresh your session before continuing.');}}
window.addEventListener('focus',changedSession);document.addEventListener('visibilitychange',changedSession);
guarded(loadSession,false);

$('progress-read').onclick=()=>{
  clearPlanSalesProgress($('progress'));
  const displayed=read,documentVersion=displayed?.document,workspace=wid,plan=planId;
  const expected={workspaceId:Number(workspace),planId:plan,version:displayed?.version,documentDigest:displayed?.document_digest,goal:documentVersion?.inputs.goal};
  guarded(async turn=>{
    const current=()=>read===displayed&&read?.document===documentVersion&&wid===workspace&&planId===plan&&!$('document').hidden&&read.version===expected.version&&read.document_digest===expected.documentDigest;
    if(!documentVersion||!current())throw new Stale();
    const response=await api(selected()+`/progress?version=${expected.version}`,turn);
    await session(turn);check(turn);if(!current())throw new Stale();
    renderPlanSalesProgress($('progress'),response,expected);
  });
};
