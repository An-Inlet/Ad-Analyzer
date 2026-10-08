const inputs=__INPUTS__;
const $=id=>document.getElementById('planning-'+id),assert=(v,m)=>{if(!v)throw Error(m);};
const until=async(fn,message)=>{const end=Date.now()+15000;while(!fn()){if(Date.now()>end)throw Error(message+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(name,value)=>{$(name).value=value;$(name).dispatchEvent(new Event('change'));};
const settled=()=>!$('list-refresh').disabled;
const realFetch=window.fetch.bind(window);let catalogs=[],mutations=[];
window.fetch=async(...args)=>{const response=await realFetch(...args),path=String(args[0]);if(path.endsWith('/target-catalog-v2')&&response.ok)catalogs.push(await response.clone().json());if(args[1]?.method==='POST'&&(/\/planning\/plans$/.test(path)||path.endsWith('/inputs')))mutations.push(JSON.parse(args[1].body));return response;};
const choice=()=>$('targets').querySelector('[data-role="target-choice"]');
const choose=value=>{const node=choice();assert(node,'target choice');node.value=value;node.dispatchEvent(new Event('change'));};
try{
 const signed=await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'goal-progress:target-browser'})});assert(signed.ok,'actual sign in');
 await import('/app/assets/planning.mjs');await until(()=>settled()&&$('workspace').options.length>1,'workspace choices');change('workspace',String(inputs.workspace_id));await until(()=>settled()&&!$('new').hidden,'owned workspace');
 $('new').click();await until(()=>settled()&&!$('editor').hidden,'editor');change('goal',inputs.goal.goal_id);const account=$('accounts').querySelector('input');account.checked=true;account.dispatchEvent(new Event('change'));
 $('milestone').value='Review native campaign targets';$('start').value=inputs.reporting_window.starts_at.slice(0,16);$('end').value=inputs.reporting_window.ends_at_exclusive.slice(0,16);
 $('targets-read').click();await until(()=>settled()&&choice(),'actual retained catalog');assert(catalogs.length===1,'one explicit read');choose('fixed');const amount=$('targets').querySelector('[data-role="target-amount"]');amount.value='0.000001';amount.dispatchEvent(new Event('input'));
 const first=catalogs[0].targets[0];$('save').click();await until(()=>settled()&&$('editor').hidden,'saved target input');assert(mutations[0].inputs.fixed_allocations[0].amount_micros===1,'exact decimal micros');assert(mutations[0].inputs.fixed_allocations[0].target.selection_key===first.selection_key,'exact original selector');
 $('generate').click();await until(()=>settled()&&$('document').textContent.includes('Plan Version 1'),'targeted generation');
 const path='/api/customer/v1/workspaces/'+inputs.workspace_id+'/planning/plans',listing=await (await realFetch(path)).json(),planId=listing.items[0].plan_id;
 const version1=await (await realFetch(path+'/'+planId)).json();assert(version1.inputs.fixed_allocations[0].target.selection_key===first.selection_key,'server persisted original target');
 $('edit').click();await until(()=>settled()&&!$('editor').hidden,'edit target revision');assert($('generate').disabled&&$('review').hidden,'draft cannot generate or report against previous inputs');
 const before=mutations.length;$('save').click();await until(()=>settled()&&$('message').textContent.includes('explicitly confirm'),'saved targets require explicit replacement');assert(mutations.length===before,'no silent target removal request');
 $('targets-read').click();await until(()=>settled()&&choice()&&catalogs.length===2,'explicit fresh read');assert(catalogs[1].targets[0].selection_key!==first.selection_key,'fresh observation differs');choose('exclude');$('replace-targets').checked=true;
 // Changing the report scope clears choices and cannot silently save an empty set.
 $('start').dispatchEvent(new Event('input'));assert(!choice(),'scope change clears native choices');$('save').click();await until(()=>settled()&&$('message').textContent.includes('Read targets again'),'scope invalidation prevents silent empty save');assert(mutations.length===before,'invalidated save has no mutation');
 $('targets-read').click();await until(()=>settled()&&choice()&&catalogs.length===3,'reselection after scope invalidation');choose('exclude');$('replace-targets').checked=true;
 const actualNow=Date.now;Date.now=()=>Date.parse(catalogs[2].expires_at);$('save').click();await until(()=>settled(),'expired selection rejected');Date.now=actualNow;assert(mutations.length===before,'browser expiry check sends no save');
 $('targets-read').click();await until(()=>settled()&&choice()&&catalogs.length===4,'explicit reread after expiry check');choose('exclude');$('replace-targets').checked=true;$('save').click();await until(()=>settled()&&$('editor').hidden,'explicit revision saved');
 assert(mutations[1].inputs.exclusions[0].selection_key===catalogs[3].targets[0].selection_key,'revised exact selector');assert(mutations[1].inputs.fixed_allocations.length===0,'explicit replacement removes fixed allocation');
 $('generate').click();await until(()=>settled()&&$('document').textContent.includes('Plan Version 2'),'revised target generation');const version2=await (await realFetch(path+'/'+planId)).json();assert(version2.inputs.excluded_entity_keys[0]===first.canonical_entity_key,'canonical exclusion stored');assert(version2.inputs.fixed_allocations.length===0,'saved replacement exact');
 $('edit').click();await until(()=>settled()&&!$('editor').hidden,'third editor');$('targets-read').click();await until(()=>settled()&&choice(),'read before session replacement');
 const rotated=await realFetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'goal-progress:target-replacement'})});assert(rotated.ok,'replacement session');$('save').click();await until(()=>$('selection').hidden,'session fence');assert(!$('targets').textContent&&!$('accounts').textContent,'session replacement clears native data');assert(mutations.length===2,'no mutation under replaced session');
 await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
