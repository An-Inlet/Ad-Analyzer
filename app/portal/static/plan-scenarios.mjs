// Independent customer budget hypotheses; never native settings or spend authority.
import {parsePlanningMicros} from './plan-target-picker.mjs';
const handles=new WeakMap(),digest=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const fail=message=>{throw Error(message);};
export function clearPlanScenarios(host){handles.delete(host);host.replaceChildren();host.hidden=true;}
export function renderPlanScenarios(host,options,onChange){
 clearPlanScenarios(host);
 const {currency,totalCeilingMicros,expiresAt,targets}=structuredClone(options),expiry=Date.parse(expiresAt);
 if(typeof currency!=='string'||!/^[A-Z]{3}$/.test(currency)||!Number.isSafeInteger(totalCeilingMicros)||totalCeilingMicros<0||totalCeilingMicros>1e15||!Number.isFinite(expiry)||expiry<=Date.now()||!Array.isArray(targets)||targets.length>8000||typeof onChange!=='function')fail('Read current targets and choose a confirmed budget first.');
 const seen=new Set();for(const {selector,label} of targets){if(!selector||!Number.isSafeInteger(selector.account_id)||selector.account_id<=0||!digest(selector.canonical_entity_key)||!digest(selector.selection_key)||seen.has(selector.canonical_entity_key)||typeof label!=='string'||label.length>1000)fail('Target choices could not be verified.');seen.add(selector.canonical_entity_key);}
 const doc=host.ownerDocument,token={},scenarios=[];let serial=0;
 const node=(tag,value)=>{const n=doc.createElement(tag);if(value!==undefined)n.textContent=value;return n;};
 const changed=()=>{if(handles.get(host)===token)onChange();};
 const button=(label,role,click)=>{const n=node('button',label);n.type='button';n.dataset.role=role;n.onclick=()=>{if(handles.get(host)!==token)return;click();changed();};return n;};
 const field=(parent,label,role)=>{const l=node('label',label),i=node('input');i.type='text';i.dataset.role=role;l.append(i);parent.append(l);i.oninput=changed;return i;};
 const list=node('div');
 const add=button('Add Budget Alternative','scenario-add',()=>{
  if(scenarios.length>=8)return;
  const block=node('fieldset'),key=`alternative_${++serial}`,title=field(block,'Alternative Name','scenario-title');title.maxLength=160;
  const rows=node('div');block.append(rows);const allocations=[];
  const reserve=field(block,`Unallocated Reserve (${currency})`,'scenario-reserve');reserve.inputMode='decimal';reserve.maxLength=23;
  const addRow=button('Add Target Allocation','scenario-row-add',()=>{
   if(allocations.length>=100)return;
   const row=node('div'),label=node('label','Target '),select=node('select');select.dataset.role='scenario-target';
   const empty=node('option','Choose A Target');empty.value='';select.append(empty);
   targets.forEach((target,index)=>{const option=node('option',target.label);option.value=String(index);select.append(option);});label.append(select);row.append(label);select.onchange=changed;
   const amount=field(row,`Planning Allocation (${currency})`,'scenario-amount');amount.inputMode='decimal';amount.maxLength=23;
   const item={select,amount};row.append(button('Remove Allocation','scenario-row-remove',()=>{allocations.splice(allocations.indexOf(item),1);row.remove();addRow.disabled=false;}));allocations.push(item);rows.append(row);addRow.disabled=allocations.length>=100;
  });
  const item={key,title,reserve,allocations};block.append(addRow,button('Remove Alternative','scenario-remove',()=>{scenarios.splice(scenarios.indexOf(item),1);block.remove();add.disabled=false;}));scenarios.push(item);list.append(block);add.disabled=scenarios.length>=8;
 });
 host.append(node('h3','Independent Budget Alternatives'),node('p',`Each alternative is your hypothesis in ${currency}, not an optimized recommendation, native budget setting or permission to spend. Allocations plus reserve must equal the confirmed ceiling separately for each alternative. Alternatives are never added together.`),list,add);host.hidden=false;handles.set(host,token);
 return Object.freeze({readIntent(now=Date.now()){
  if(handles.get(host)!==token||!Number.isFinite(now)||now>=expiry)fail('Budget alternative targets expired or changed. Read targets and rebuild alternatives.');
  return scenarios.map(item=>{
   const title=item.title.value.trim();if(!title||title.length>160)fail('Name each budget alternative.');
   const used=new Set();let sum=0n;
   const allocations=item.allocations.map(row=>{
    if(!/^(0|[1-9][0-9]*)$/.test(row.select.value))fail('Choose each alternative target.');
    const target=targets[Number(row.select.value)];if(!target||used.has(target.selector.canonical_entity_key))fail('Choose each target only once per alternative.');used.add(target.selector.canonical_entity_key);
    const amount=parsePlanningMicros(row.amount.value);sum+=amount;return{target:{...target.selector},amount_micros:Number(amount)};
   });
   const reserve=parsePlanningMicros(item.reserve.value);if(sum+reserve!==BigInt(totalCeilingMicros))fail('Each alternative must independently equal the confirmed ceiling, including reserve.');
   return{key:item.key,title,allocations,unallocated_micros:Number(reserve)};
  });
 }});
}
