const $=id=>document.getElementById('planning-'+id),assert=(v,m)=>{if(!v)throw Error(m);},nativeFetch=window.fetch,planId='a'.repeat(32),goalId='b'.repeat(32),none={advertising_writes_enabled:false,spending_authority:'none'},calls=[];
let policy=6,mode='null';
const wait=async(predicate,label)=>{const end=Date.now()+2500;while(Date.now()<end){if(predicate())return;await new Promise(r=>setTimeout(r,10));}throw Error(label+': '+$('message').textContent);};
function inputs(){return{workspace_id:1,plan_id:planId,revision:1,goal:{goal_id:goalId},accounts:[{account_id:1}],excluded_entity_keys:[],fixed_allocations:[],scenario_intents:[],milestone:'Grow Mug Sales',product_offer:null,constraints:[],assumptions:[],reporting_window:{starts_at:'2026-10-01T00:00:00Z',ends_at_exclusive:'2026-10-02T00:00:00Z'},comparison_window:null,maximum_creative_assets:0,creative:null,selected_reporting:[],...(mode==='omitted'?{}:{google_daily_budget_intents:mode==='empty'?[]:null})};}
window.fetch=async(url,init={})=>{
 const path=String(url),method=init.method??'GET';calls.push({path,method});let value;
 if(path==='/api/customer/v1/session')value={user_id:'alice'};
 else if(path==='/api/customer/v1/workspaces')value=[{id:1,name:'Mug Brand',role:'owner'}];
 else if(path.endsWith('/goals'))value=[{id:goalId,workspace_id:1,revision:1,confirmation_recorded:true,confirmed_at:'2026-10-01T00:00:00Z',definition:{milestone:'Grow Mug Sales',budget_micros:1000000000,aggressiveness:'balanced',target_window:{currency:'USD'}}}];
 else if(path.endsWith('/planning/accounts'))value={complete:true,accounts:[{id:1,name:'Mug Google',platform:'google_ads'}]};
 else if(path.endsWith('/capabilities'))value={schema_version:'inlet.planning-capabilities.v1',workspace_id:1,policy_version:`inlet.descriptive-review.v${policy}`,generator_version:`inlet.descriptive-planning.v${policy}`,selected_reporting_available:true,...none};
 else if(path.endsWith('/media'))value=[];
 else if(path.includes('/versions?'))value={items:[],next_cursor:null,...none};
 else if(path.endsWith('/plans/'+planId))value={plan_id:planId,input_revision:1,version:0,event_sequence:0,inputs:inputs(),document:null,...none};
 else if(path.endsWith('/plans?limit=20'))value={items:[{plan_id:planId,version:0,input_revision:1,...none}],next_cursor:null};
 else throw Error('Unexpected controlled request '+path);
 return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
};
async function chooseSaved(){
 $('refresh').click();await wait(()=>!$('selection').hidden&&!$('workspace').disabled,'session');$('workspace').value='1';$('workspace').dispatchEvent(new Event('change'));await wait(()=>$('plans').querySelector('button')&&!$('plans').querySelector('button').disabled,'plan list');$('plans').querySelector('button').click();await wait(()=>!$('edit').hidden&&!$('edit').disabled,'saved read');
}
try{
 await import('/app/assets/planning.mjs');await wait(()=>!$('selection').hidden&&!$('workspace').disabled,'initial session');
 for(const variant of ['null','omitted']){policy=6;mode=variant;await chooseSaved();const before=calls.length;$('edit').click();await wait(()=>$('message').textContent==='This saved plan predates shared budget reviews. Read its history or prepare a new plan; its saved inputs have not been upgraded.','legacy refusal');assert($('editor').hidden&&$('goal').options.length===1&&$('accounts').children.length===0,'legacy editor remains hidden and unpopulated');assert(!calls.slice(before).some(c=>c.path.endsWith('/media')||c.path.includes('google-budget-owners')||c.method!=='GET'),'legacy refusal before media/discovery/mutation');}
 for(const [version,inputMode] of [[5,'null'],[6,'empty']]){policy=version;mode=inputMode;await chooseSaved();$('edit').click();await wait(()=>!$('editor').hidden&&!$('save').disabled,'compatible saved editor');assert($('editor-title').textContent==='Edit Plan Inputs','compatible edit preserved');assert(document.getElementById('google-owner-inputs').hidden===(version===5),'exact capability owner controls');$('cancel').click();}
 policy=6;mode='null';$('new').click();await wait(()=>!$('editor').hidden&&!$('save').disabled,'new V6 editor');assert($('editor-title').textContent==='Prepare A New Plan'&&!document.getElementById('google-owner-inputs').hidden,'new V6 still available');assert(calls.every(c=>c.method==='GET')&&!calls.some(c=>c.path.includes('google-budget-owners')),'opening editors does not discover or mutate');
 await nativeFetch('/result',{method:'POST',body:'PASS'});
}catch(error){await nativeFetch('/result',{method:'POST',body:error.stack||String(error)});}finally{window.fetch=nativeFetch;}
