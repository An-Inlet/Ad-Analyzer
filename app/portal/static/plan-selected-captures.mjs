import {planningCapability} from './plan-capability.mjs';
// Exact customer choices only. Availability is descriptive; the server revalidates every save.
const active=new WeakMap();
export function clearSelectedCaptures(host){active.delete(host);host.replaceChildren();host.hidden=true;}
export function renderSelectedCaptures(host,{capability,workspaceId,accounts,saved=null}){
  clearSelectedCaptures(host);const token={};active.set(host,token);const current=()=>{if(active.get(host)!==token)throw Error('Capture choices changed. Review the current editor.');};
  const canonical=planningCapability(capability,workspaceId).selected;
  if(!Array.isArray(accounts)||accounts.length>20||accounts.some(a=>!Number.isSafeInteger(a.id)||a.id<=0)||new Set(accounts.map(a=>a.id)).size!==accounts.length)throw Error('Account choices could not be verified.');
  if(!canonical){if(saved!==null&&saved!==undefined)throw Error('This saved plan requires selected reporting, which is currently unavailable.');return{readIntent:()=>{current();return undefined;}};}
  if(saved!==null&&(!Array.isArray(saved)||saved.length>20))throw Error('Saved capture choices could not be verified.');
  const byAccount=new Map(accounts.map(a=>[a.id,a])),values=new Map();
  for(const item of saved??[]){if(!Number.isSafeInteger(item.account_id)||!byAccount.has(item.account_id)||values.has(item.account_id)||typeof item.capture_id!=='string'||!/^[a-f0-9]{32}$/.test(item.capture_id))throw Error('A saved capture account is unavailable. Review the original plan before editing.');values.set(item.account_id,item.capture_id);}
  const title=document.createElement('h3');title.textContent='Selected Reporting Captures';host.append(title);
  const help=document.createElement('p');help.textContent='Apply a capture brought from Reporting Reads, or copy its Capture ID for each account you choose. Reporting Reads supports selected-event captures for Google Ads when reporting access is available. Leave an account blank to plan without its selected conversion observations. Blank does not mean zero conversions. Review that your captured range covers both reporting periods.';host.append(help);
  const fields=[];
  for(const account of accounts){const label=document.createElement('label'),input=document.createElement('input');input.type='text';input.maxLength=32;input.autocomplete='off';input.spellcheck=false;input.dataset.captureAccount=String(account.id);input.value=values.get(account.id)??'';label.append(document.createTextNode(`${account.name} · Capture ID (Optional)`),input);host.append(label);fields.push({accountId:account.id,input});}
  host.hidden=false;
  return{applyHint(hint,selectedAccounts){current();const field=fields.find(f=>f.accountId===hint.accountId);if(saved!==null||hint.workspaceId!==workspaceId||!field||!selectedAccounts.includes(hint.accountId)||byAccount.get(hint.accountId).platform!=='google_ads'||!/^[a-f0-9]{32}$/.test(hint.captureId))throw Error('Choose the matching Google Ads account in a new plan before applying this capture.');if(field.input.value!=='')throw Error('The capture field already contains a choice. Clear it explicitly before applying another capture.');field.input.value=hint.captureId;},readIntent(selectedAccounts){current();const chosen=new Set(selectedAccounts),result=[];for(const{accountId,input}of fields){const value=input.value.trim();if(!value)continue;if(!chosen.has(accountId))throw Error('Clear the capture ID explicitly before removing its account.');if(!/^[a-f0-9]{32}$/.test(value))throw Error('Enter the exact 32-character Capture ID from Reporting Reads.');result.push({account_id:accountId,capture_id:value});}return result;}};
}
