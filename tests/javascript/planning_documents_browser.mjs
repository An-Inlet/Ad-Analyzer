const inputs=__INPUTS__;
const $=id=>document.getElementById('planning-'+id),assert=(v,m)=>{if(!v)throw Error(m);};
const until=async(fn,message)=>{const end=Date.now()+15000;while(!fn()){if(Date.now()>end)throw Error(message+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const change=(name,value)=>{$(name).value=value;$(name).dispatchEvent(new Event('change'));};
const settled=()=>!$('list-refresh').disabled;
try{
 const response=await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'goal-progress:browser'})});assert(response.ok,'real sign in');
 await import('/app/assets/planning.mjs');await until(()=>settled()&&$('workspace').options.length>1,'workspaces');
 change('workspace',String(inputs.workspace_id));await until(()=>settled()&&!$('new').hidden,'workspace plans');
 $('new').click();await until(()=>settled()&&!$('editor').hidden,'input editor');
 change('goal',inputs.goal.goal_id);const account=$('accounts').querySelector('input');assert(account,'actual owned account');account.checked=true;
 $('milestone').value='Review <img src=x onerror="window.injected=true"> bottle sales';$('product').value='Reusable bottle';
 $('start').value=inputs.reporting_window.starts_at.slice(0,16);$('end').value=inputs.reporting_window.ends_at_exclusive.slice(0,16);
 const realFetch=window.fetch.bind(window);let lost=false,posts=0;
 window.fetch=async(...args)=>{const path=String(args[0]),method=args[1]?.method??'GET';const response=await realFetch(...args);if(path.endsWith('/planning/plans')&&method==='POST'){posts++;if(!lost){lost=true;throw Error('Simulated response loss after actual commit');}}return response;};
 $('save').click();await until(()=>settled()&&!$('pending').hidden,'uncertain save result');assert(posts===1,'single actual POST');assert($('save').disabled,'pending prevents another save');
 $('recover').click();await until(()=>settled()&&$('pending').hidden&&!$('current').hidden,'actual receipt lookup');assert(posts===1,'lookup never reposts');
 $('generate').click();await until(()=>settled()&&!$('document').hidden,'actual generation');
 assert($('document').textContent.includes('Plan Version 1'),'version1');assert($('document').textContent.includes('<img src=x'),'literal hostile text');assert(!$('document').querySelector('img,script')&&!window.injected,'safe document');

 const record=async(type,statement)=>{
   change('action',$('action').options[1].value);change('record-type',type);$('statement').value=statement;
   if(type==='customer_reports_applied')$('applied').value=new Date().toISOString().slice(0,16);
   if(type==='retracted')change('prior',$('prior').options[1].value);
   $('confirm-review').checked=true;$('confirm-review').dispatchEvent(new Event('change'));
   assert(!$('record').disabled,'eligible customer record');$('record').click();
   await until(()=>settled()&&$('message').textContent.includes('customer record was saved'),'saved customer record');
 };
 await record('accepted_for_manual_application','I reviewed this action');
 assert($('events').textContent.includes('Accepted For Manual Application'),'decision history');
 await record('customer_reports_applied','I applied this outside Inlet');
 assert($('events').textContent.includes('Not Independently Verified'),'report remains unverified');
 await record('retracted','I am withdrawing the previous report');
 assert($('events').textContent.includes('Customer Report Retracted'),'immutable withdrawal');
 $('edit').click();await until(()=>settled()&&!$('editor').hidden,'revision editor');$('milestone').value='Review updated bottle sales';$('save').click();await until(()=>settled()&&$('editor').hidden,'saved revision');
 $('generate').click();await until(()=>settled()&&$('document').textContent.includes('Plan Version 2'),'successor');
 $('compare').click();await until(()=>settled()&&!$('comparison').hidden,'actual comparison');assert($('comparison').textContent.includes('Review updated bottle sales'),'diff actual milestone');
 $('events-refresh').click();await until(()=>settled()&&!$('events').hidden,'actual history');assert($('events').textContent.includes('Customer Report Retracted'),'historical customer records preserved');

 let rotated=false;
 window.fetch=async(...args)=>{
   const path=String(args[0]),method=args[1]?.method??'GET',response=await realFetch(...args);
   if(!rotated&&/\/planning\/plans\/[a-f0-9]{32}$/.test(path)&&method==='GET'){
     rotated=true;const next=await realFetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'goal-progress:rotated'})});assert(next.ok,'actual replacement session');
   }
   return response;
 };
 $('read').click();await until(()=>rotated&&$('selection').hidden,'old operation rejected after session replacement');
 assert($('document').hidden&&!$('document').textContent&&!$('events').textContent&&!$('accounts').textContent,'old session data cleared');
 $('refresh').click();await until(()=>settled()&&$('workspace').options.length>1,'refresh replacement session');
 change('workspace',String(inputs.workspace_id));await until(()=>settled()&&$('plans').querySelector('button'),'retained plan under replacement session');
 $('plans').querySelector('button').click();await until(()=>settled()&&!$('document').hidden,'authorized reread under replacement session');
 $('logout').click();await until(()=>$('message').textContent==='Signed out.','logout');assert($('document').hidden&&!$('document').textContent&&$('events').hidden&&!$('events').textContent,'logout clears documents');
 await realFetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
