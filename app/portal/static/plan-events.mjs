// Immutable customer history and separate field observations, never execution state.
import {validateObservation,appendObservation,observationLabels} from './plan-observations.mjs';
const decisions={accepted_for_manual_application:'Accepted For Manual Application',rejected:'Rejected',deferred:'Deferred'};
const assertions={customer_reports_applied:'Customer Reports Applied',retracted:'Customer Report Retracted'};
const id=value=>typeof value==='string'&&/^[a-f0-9]{32}$/.test(value);
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const positive=value=>Number.isSafeInteger(value)&&value>0;
const bounded=value=>typeof value==='string'&&value.length>0&&value.length<=2000;
const noAuthority=value=>value?.advertising_writes_enabled===false&&value.spending_authority==='none';
const stamp=value=>new Date(value).toLocaleString(undefined,{timeZone:'UTC'})+' UTC';
const fail=()=>{throw Error('The customer history response could not be verified. Read it again when ready.');};
export function clearPlanEvents(host){host.replaceChildren();host.hidden=true;}
export function renderPlanEvents(host,page,{workspaceId,planId,afterSequence=0}){
  clearPlanEvents(host);
  if(!positive(workspaceId)||!id(planId)||!Number.isSafeInteger(afterSequence)||afterSequence<0||!noAuthority(page)||!Array.isArray(page.items)||page.items.length>100||(page.next_cursor!==null&&(typeof page.next_cursor!=='string'||!page.next_cursor.length||page.next_cursor.length>256)))fail();
  let previous=afterSequence;const seen=new Set();
  for(const row of page.items){
    const e=row?.event,decision=Object.hasOwn(e??{},'decision'),assertion=Object.hasOwn(e??{},'assertion'),observation=Object.hasOwn(e??{},'status');
    if(!noAuthority(row)||!positive(row.event_sequence)||row.event_sequence<=previous||!noAuthority(e)||e.workspace_id!==workspaceId||e.plan_id!==planId||!positive(e.version)||!id(e.event_id)||seen.has(e.event_id)||!digest(e.document_digest)||!digest(e.action_digest)||typeof e.action_key!=='string'||!(/^[a-z][a-z0-9_:-]{0,95}$/).test(e.action_key)||Number(decision)+Number(assertion)+Number(observation)!==1)fail();
    if(observation){validateObservation(e);seen.add(e.event_id);previous=row.event_sequence;continue;}
    if(!id(e.actor_id)||typeof e.recorded_at!=='string'||!Number.isFinite(Date.parse(e.recorded_at))||(e.supersedes_event_id!==null&&(!id(e.supersedes_event_id)||e.supersedes_event_id===e.event_id))||['observed_at','comparisons','limitations','causality','applied_by'].some(k=>Object.hasOwn(e,k)))fail();
    if(decision){if(!Object.hasOwn(decisions,e.decision)||!bounded(e.reason))fail();}
    else {
      if(!Object.hasOwn(assertions,e.assertion)||e.verification!=='customer_report_only'||!bounded(e.statement))fail();
      if(e.assertion==='retracted'){if(e.reported_applied_at!==null||e.supersedes_event_id===null)fail();}
      else if(typeof e.reported_applied_at!=='string'||!Number.isFinite(Date.parse(e.reported_applied_at))||Date.parse(e.reported_applied_at)>Date.parse(e.recorded_at))fail();
    }
    seen.add(e.event_id);previous=row.event_sequence;
  }
  const doc=host.ownerDocument,fragment=doc.createDocumentFragment();
  const text=(tag,value)=>{const node=doc.createElement(tag);node.textContent=String(value);return node;};
  fragment.append(text('h2','Decisions, Reports And Field Observations'),text('p','This page contains immutable customer history. A decision records review; a customer application report is not independently verified. Field observations are separate evidence, not customer assertions. Neither establishes who made a provider change or its effect. Earlier records remain visible after correction.'));
  if(afterSequence>0)fragment.append(text('p',`Continuation after event ${afterSequence}. Earlier records are on preceding pages.`));
  const list=doc.createElement('ol');
  for(const row of page.items){
    const e=row.event,item=doc.createElement('li'),isDecision=Object.hasOwn(e,'decision'),isObservation=Object.hasOwn(e,'status');
    item.append(text('h3',`Event ${row.event_sequence} · ${isObservation?observationLabels[e.status]:isDecision?decisions[e.decision]:assertions[e.assertion]}`),text('p',`Plan Version ${e.version} · Action ${e.action_key}`));
    if(isObservation)appendObservation(item,e,text,stamp);
    else{
      item.append(text('p',`Recorded ${stamp(e.recorded_at)}`),text('p',isDecision?e.reason:e.statement));
      if(!isDecision){item.append(text('p','Customer Report Only — Not Independently Verified'));if(e.reported_applied_at!==null)item.append(text('p',`Customer-Reported Application Time: ${stamp(e.reported_applied_at)}`));}
    }
    const details=doc.createElement('dl');
    const entries=[['Event ID',e.event_id],['Document Digest',e.document_digest],['Action Digest',e.action_digest]];
    if(!isObservation)entries.push(['Customer ID',e.actor_id],['Replaces Event',e.supersedes_event_id??'None']);
    for(const [label,value] of entries)details.append(text('dt',label),text('dd',value));
    item.append(details);list.append(item);
  }
  fragment.append(list);
  if(!page.items.length)fragment.append(text('p','No decisions, reports or observations were returned on this page.'));
  fragment.append(text('p',page.next_cursor===null?'End of the returned history.':'More customer history is available. This page is incomplete.'));
  host.replaceChildren(fragment);host.hidden=false;
  return {lastSequence:previous,nextCursor:page.next_cursor};
}
