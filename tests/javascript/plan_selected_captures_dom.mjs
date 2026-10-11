import {renderSelectedCaptures,clearSelectedCaptures} from './plan-selected-captures.mjs';
const host=document.querySelector('#host'),assert=(v,m)=>{if(!v)throw Error(m);},rejects=(fn,m)=>{let failed=false;try{fn();}catch{failed=true;}assert(failed,m);};
const cap={schema_version:'inlet.planning-capabilities.v1',workspace_id:1,policy_version:'inlet.descriptive-review.v4',generator_version:'inlet.descriptive-planning.v4',selected_reporting_available:true,advertising_writes_enabled:false,spending_authority:'none'};
const options={capability:cap,workspaceId:1,accounts:[{id:2,name:'<img src=x onerror=alert(1)>'}],saved:null},id='a'.repeat(32);
try{
 let handle=renderSelectedCaptures(host,options);assert(!host.querySelector('img'),'literal labels');assert(JSON.stringify(handle.readIntent([2]))==='[]','explicit empty');
 host.querySelector('input').value=id;assert(JSON.stringify(handle.readIntent([2]))===JSON.stringify([{account_id:2,capture_id:id}]),'exact pair');rejects(()=>handle.readIntent([]),'unchecked account requires explicit clear');
 host.querySelector('input').value='invalid';rejects(()=>handle.readIntent([2]),'invalid id');
 handle=renderSelectedCaptures(host,{...options,saved:[{account_id:2,capture_id:id}]});assert(host.querySelector('input').value===id,'saved exact');clearSelectedCaptures(host);rejects(()=>handle.readIntent([2]),'clear revokes');
 handle=renderSelectedCaptures(host,options);renderSelectedCaptures(host,options);rejects(()=>handle.readIntent([2]),'rerender revokes');
 rejects(()=>renderSelectedCaptures(host,{...options,saved:[{account_id:3,capture_id:id}]}),'foreign saved account');
 rejects(()=>renderSelectedCaptures(host,{...options,workspaceId:2}),'wrong workspace');
 rejects(()=>renderSelectedCaptures(host,{...options,capability:{...cap,advertising_writes_enabled:true}}),'no authority');
 const legacy={...options,capability:{...cap,policy_version:'inlet.descriptive-review.v3',generator_version:'inlet.descriptive-planning.v3',selected_reporting_available:false}};
 assert(renderSelectedCaptures(host,legacy).readIntent([2])===undefined&&host.hidden,'legacy unchanged');rejects(()=>renderSelectedCaptures(host,{...legacy,saved:[]}),'selected edit cannot silently become legacy');
 await fetch('/result',{method:'POST',body:'PASS'});
}catch(error){await fetch('/result',{method:'POST',body:error.stack||String(error)});}
