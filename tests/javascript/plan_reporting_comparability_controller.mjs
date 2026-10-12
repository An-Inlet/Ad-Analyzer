const mode='__MODE__',$=id=>document.getElementById('planning-'+id),assert=(v,m)=>{if(!v)throw Error(m);},native=window.fetch,none={advertising_writes_enabled:false,spending_authority:'none'},calls=[];
const plan=await(await native('/plan.json')).json(),wid=plan.inputs.workspace_id,pid=plan.inputs.plan_id;
let delayed=false,release=null,interrupted=false;
const wait=async(fn,label)=>{const end=Date.now()+3000;while(!fn()){if(Date.now()>end)throw Error(label+': '+$('message').textContent);await new Promise(r=>setTimeout(r,10));}};
window.fetch=async(url,init={})=>{
 const path=String(url);calls.push({path,method:init.method??'GET'});let value;
 if(path==='/api/customer/v1/session')value={user_id:'alice'};
 else if(path==='/api/customer/v1/workspaces')value=[{id:wid,name:'Original',role:'owner'},{id:wid+100,name:'Other',role:'owner'}];
 else if(path.includes('/versions?'))value={items:[{plan_id:pid,version:1,...none}],next_cursor:null,...none};
 else if(path.endsWith('/plans?limit=20'))value={items:[{plan_id:pid,version:1,input_revision:plan.inputs.revision,...none}],next_cursor:null};
 else if(path.endsWith('/plans/'+pid)){
  if(interrupted){interrupted=false;throw TypeError('synthetic interrupted read');}
  if(delayed)await new Promise(resolve=>{release=resolve;});
  value={plan_id:pid,inputs:plan.inputs,input_revision:plan.inputs.revision,version:1,event_sequence:0,document:plan,document_digest:'a'.repeat(64),freshness:'current',reasons:[],...none};
 }else throw Error('Unexpected controlled request '+path);
 return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
};
const settled=()=>!$('list-refresh').disabled;
async function choose(value){$('workspace').value=String(value);$('workspace').dispatchEvent(new Event('change'));await wait(settled,'workspace read');}
async function open(){ $('plans').querySelector('button').click();await wait(()=>settled()&&!$('document').hidden,'plan read');}
try{
 await import('/app/assets/planning.mjs');await wait(()=>settled()&&!$('selection').hidden,'session');await choose(wid);await open();
 let pane=$('document').querySelector('#planning-reporting-comparability');assert(pane,'actual controller renders review');const count=calls.length;pane.querySelector('summary').click();assert(pane.querySelector('details').open,'explicit expand');pane.querySelector('summary').click();assert(!pane.querySelector('details').open&&calls.length===count,'toggle has no requests');
 pane.querySelector('details').open=true;$('read').click();await wait(()=>settled()&&!$('document').hidden,'repeated read');assert(!$('document').querySelector('details').open,'repeated read resets local state');
 interrupted=true;$('read').click();await wait(()=>settled()&&$('document').hidden,'interrupted read clears basis');assert(!$('document').querySelector('#planning-reporting-comparability'),'interrupted basis gone');$('read').click();await wait(()=>settled()&&!$('document').hidden,'explicit retry');
 delayed=true;$('read').click();await wait(()=>release!==null,'pending read');
 if(mode==='workspace'){$('workspace').value=String(wid+100);$('workspace').dispatchEvent(new Event('change'));}
 else{document.cookie='fixture_session=replaced; Path=/';window.dispatchEvent(new Event('focus'));}
 assert($('document').hidden&&!$('document').childNodes.length,'scope change immediately clears entire review');delayed=false;release();await new Promise(r=>setTimeout(r,30));assert($('document').hidden&&!$('document').childNodes.length,'late old response cannot restore basis');
 if(mode==='session'){$('refresh').click();await wait(()=>settled()&&!$('selection').hidden,'replacement session');}else await wait(settled,'other workspace');
 await choose(wid);await open();assert(!$('document').querySelector('#planning-reporting-comparability details').open,'fresh explicit read starts closed');assert(calls.every(c=>c.method==='GET'),'no save/generation from review');
 await native('/result',{method:'POST',body:'PASS'});
}catch(error){await native('/result',{method:'POST',body:error.stack||String(error)});}finally{window.fetch=native;}
