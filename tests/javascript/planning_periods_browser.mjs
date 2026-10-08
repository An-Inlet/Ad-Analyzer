const inputs=__INPUTS__;
const $=id=>document.getElementById('planning-'+id),assert=(v,m)=>{if(!v)throw Error(m);};
const until=async(fn,message)=>{const end=Date.now()+15000;while(!fn()){if(Date.now()>end)throw Error(message+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(name,value)=>{$(name).value=value;$(name).dispatchEvent(new Event('change'));};
const settled=()=>!$('list-refresh').disabled,realFetch=window.fetch.bind(window);
let mutations=[],catalogs=0,rotate=false,planPath='';
window.fetch=async(...args)=>{
 const response=await realFetch(...args),path=String(args[0]);
 if(path.endsWith('/target-catalog-v2')&&response.ok)catalogs++;
 if(args[1]?.method==='POST'&&(/\/planning\/plans$/.test(path)||path.endsWith('/inputs')))mutations.push(JSON.parse(args[1].body));
 if(rotate&&path===planPath&&args[1]?.method==='GET'){rotate=false;assert((await realFetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'goal-progress:periods-replaced'})})).ok,'actual replacement session');}
 return response;
};
const comparison=enabled=>{$('comparison-enabled').checked=enabled;$('comparison-enabled').dispatchEvent(new Event('change'));};
const checkJSON=async response=>{assert(response.ok,'actual API success '+response.status);return response.json();};
try{
 assert((await realFetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'goal-progress:periods-browser'})})).ok,'real sign in');
 await import('/app/assets/planning.mjs');await until(()=>settled()&&$('workspace').options.length>1,'session');change('workspace',String(inputs.workspace_id));await until(()=>settled()&&!$('new').hidden,'workspace');
 $('new').click();await until(()=>settled()&&!$('editor').hidden,'new editor');assert(!$('comparison-enabled').checked&&$('comparison-fields').hidden,'comparison optional by default');
 change('goal',inputs.goal.goal_id);$('accounts').querySelector('input').checked=true;$('milestone').value='Compare exact periods';$('start').value=inputs.reporting_window.starts_at.slice(0,16);$('end').value=inputs.reporting_window.ends_at_exclusive.slice(0,16);
 $('targets-read').click();await until(()=>settled()&&$('targets').querySelector('[data-role="target-choice"]'),'read owned targets');const targets=$('targets').textContent;
 comparison(true);$('comparison-end').value=$('start').value;$('comparison-start').value=new Date(Date.parse(inputs.reporting_window.starts_at)-86400000).toISOString().slice(0,16);$('comparison-start').dispatchEvent(new Event('input'));assert($('targets').textContent===targets&&catalogs===1,'comparison retains same primary catalog');
 $('start').dispatchEvent(new Event('input'));assert(!$('targets').textContent,'primary change clears catalog');$('targets-read').click();await until(()=>settled()&&catalogs===2&&$('targets').textContent,'primary explicit reread');
 $('save').click();await until(()=>settled()&&$('editor').hidden&&!$('current').hidden,'create with comparison');assert(mutations.length===1&&mutations[0].inputs.comparison_window,'comparison in actual request');
 $('generate').click();await until(()=>settled()&&!$('document').hidden,'first version');
 const root='/api/customer/v1/workspaces/'+inputs.workspace_id+'/planning/plans',listing=await checkJSON(await realFetch(root));planPath=root+'/'+listing.items[0].plan_id;
 const first=await checkJSON(await realFetch(planPath+'/export?version=1'));
 const precise=structuredClone(mutations[0].inputs);precise.reporting_window.starts_at=precise.reporting_window.starts_at.replace('.000Z','.000001Z');precise.comparison_window.ends_at_exclusive=precise.reporting_window.starts_at;precise.comparison_window.starts_at=precise.comparison_window.starts_at.replace('.000Z','.000002Z');
 const csrf=document.cookie.split(';').map(v=>v.trim()).find(v=>v.startsWith('__Host-inlet_csrf=')).split('=')[1];
 await checkJSON(await realFetch(planPath+'/inputs',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({request_key:crypto.randomUUID().replaceAll('-',''),expected_input_revision:1,expected_version:1,inputs:precise})}));
 const stored=await checkJSON(await realFetch(planPath));assert(stored.inputs.reporting_window.starts_at.includes('.000001')&&stored.inputs.comparison_window.starts_at.includes('.000002'),'server retained microseconds');
 $('edit').click();await until(()=>settled()&&!$('editor').hidden,'edit exact saved periods');assert($('comparison-enabled').checked&&!$('comparison-fields').hidden,'saved comparison restored');$('milestone').value='Preserve exact saved period instants';$('save').click();await until(()=>settled()&&$('editor').hidden,'save precision');
 assert(mutations.length===2&&JSON.stringify(mutations[1].inputs.reporting_window)===JSON.stringify(stored.inputs.reporting_window)&&JSON.stringify(mutations[1].inputs.comparison_window)===JSON.stringify(stored.inputs.comparison_window),'unchanged controls preserve microseconds');
 $('generate').click();await until(()=>settled()&&$('document').textContent.includes('Plan Version 2'),'second version');const second=await checkJSON(await realFetch(planPath+'/export?version=2'));assert(second.document.inputs.comparison_window,'artifact contains comparison');const previous=await checkJSON(await realFetch(planPath+'/export?version=1'));assert(previous.document_digest===first.document_digest&&JSON.stringify(previous.document)===JSON.stringify(first.document),'historical artifact unchanged');
 $('edit').click();await until(()=>settled()&&!$('editor').hidden,'remove comparison');comparison(false);assert($('comparison-fields').hidden&&$('comparison-start').disabled,'disabled comparison controls');$('save').click();await until(()=>settled()&&$('editor').hidden,'explicit removal');assert(mutations.length===3&&mutations[2].inputs.comparison_window===null,'explicit removal submits null');
 rotate=true;$('edit').click();await until(()=>!rotate&&$('selection').hidden,'late old-session response rejected');assert($('editor').hidden&&!$('comparison-enabled').checked&&!$('comparison-start').value&&!$('comparison-end').value,'session clears period state');assert(mutations.length===3,'session race causes no write');
 await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
