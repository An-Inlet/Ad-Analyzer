// Frozen JSON-port browser test. Real HTTPS/session APIs; automation responses
// are controlled fixtures until the backend route package is frozen.
const $=id=>document.getElementById('opt-'+id),assert=(ok,msg)=>{if(!ok)throw new Error(msg);};
const until=async(test,msg)=>{const end=Date.now()+15000;while(!await test()){if(Date.now()>end)throw new Error(msg+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const settled=()=>!$('refresh').disabled;
const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change'));};
const acknowledge=()=>{$('auto-check').checked=true;$('auto-check').dispatchEvent(new Event('change'));};
const native=window.fetch,requests=[];
const binding={mandate_id:'1'.repeat(32),revision:2,consent_id:'2'.repeat(32),policy_digest:'3'.repeat(64),ledger_id:'4'.repeat(32),environment:'contract_test'};
const capabilities={available:true,reason:'ready',session_bound:true,message:'Offline Contract Test · Registered Policy Available',mandates:[{mandate:binding,label:'Brand Search <img src=x>',currency:'USD',total_limit_micros:90000000,starts_at:'2026-10-01T00:00:00Z',ends_at:'2026-11-01T00:00:00Z'}],policies:[{policy:{policy_id:'fixture-budget',revision:3},label:'Budget Policy <img src=x>',environment:'contract_test'}]};
let runs=[],hold=null,entered=false,released=null,lose='',available=true,denied=false;
const reply=value=>new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
window.fetch=async(...args)=>{
const url=String(args[0]),opts=args[1]||{},method=opts.method||'GET';
if(!url.includes('/execution/automation/'))return native(...args);
requests.push({url,method,body:opts.body,headers:opts.headers});
if(denied)return new Response('{}',{status:403});
let value;
if(url.endsWith('/capabilities'))value=available?capabilities:{...capabilities,available:false,reason:'automation_not_available',message:'Session automation is unavailable.',policies:[],mandates:[]};
else if(url.endsWith('/runs'))value={runs};
else if(url.endsWith('/start')){assert(method==='POST','explicit Start POST');const body=JSON.parse(opts.body);assert(JSON.stringify(body)===JSON.stringify({mandate:binding,policy:capabilities.policies[0].policy}),'only exact projected mandate/policy submitted');assert(opts.headers['X-CSRF-Token']?.length===43,'same-origin CSRF');value={run_id:'a'.repeat(32),status:'running',reason:'ready',environment:'contract_test',session_bound:true,message:'Runs only while the original session remains valid.'};runs=[value];}
else if(url.endsWith('/stop')){assert(method==='POST'&&opts.body===undefined,'Stop has no financial or proof body');value={...runs[0],status:'stopped',reason:'customer_stopped',message:'Future automatic changes stopped. Existing effects remain unchanged.'};runs=[value];}
else value=runs[0];
if(hold&&url.endsWith(hold)){entered=true;await new Promise(resolve=>released=resolve);hold=null;}
if(lose&&url.endsWith(lose)){lose='';throw new TypeError('fixture response lost after acceptance');}
return reply(value);
};
try{
assert((await native('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'optimization-owner:browser'})})).ok,'actual owner login');
await import('/app/assets/optimization.mjs');await until(()=>$('workspace').options.length===2&&settled(),'workspace');
async function workspace(){change('workspace','__WORKSPACE__');await until(()=>settled()&&$('auto-policy').options.length===2,'automation options');}
function select(){change('auto-mandate',$('auto-mandate').options[1].value);change('auto-policy',$('auto-policy').options[1].value);acknowledge();}
await workspace();assert($('auto-start').disabled,'no implicit Start or selection');assert($('auto-capabilities').textContent.includes('Contract Test'),'honest fixture environment');assert(!$('auto-check').checked,'no consent default');select();assert(!$('auto-start').disabled,'explicit reviewed selections enable Start');assert($('auto-mandate-summary').textContent.includes('90.000000 USD')&&$('auto-mandate-summary').textContent.includes('2026-11-01'),'exact overall cap and period');assert(!document.querySelector('img'),'server labels escaped');
// A -> B -> A context change invalidates a successful late Start result.
hold='/start';$('auto-start').click();await until(()=>entered,'Start held');change('workspace','');await until(settled,'clear old workspace');await workspace();released();await until(settled,'late response settled');assert(!$('auto-status').textContent.includes('Runs only while'),'late success cannot select old result');assert($('auto-stop').disabled,'old result cannot become actionable after ABA');assert(requests.filter(r=>r.url.endsWith('/start')).length===1,'no automatic mutation retry');
// Owned history is readable after the lost/late result; no replacement Start.
change('auto-run','a'.repeat(32));await until(()=>settled()&&!$('auto-stop').disabled,'owned status recovery');lose='/stop';$('auto-stop').click();await until(()=>settled()&&$('auto-status').textContent.includes('uncertain'),'lost Stop response');assert($('auto-stop').disabled&&$('auto-start').disabled,'uncertain mutation blocks repeat');$('auto-refresh').click();await until(settled,'history recovery');change('auto-run','a'.repeat(32));await until(()=>settled()&&$('auto-status').textContent.includes('Stopped'),'stopped recovered');assert(requests.filter(r=>r.url.endsWith('/stop')).length===1,'no replay after lost Stop');
// Lost Start is recovered by a read, not a second Start.
select();lose='/start';$('auto-start').click();await until(()=>settled()&&$('auto-status').textContent.includes('uncertain'),'lost Start response');$('auto-refresh').click();await until(settled,'refresh saved automation');change('auto-run','a'.repeat(32));await until(()=>settled()&&!$('auto-stop').disabled,'lost Start recovered');assert(requests.filter(r=>r.url.endsWith('/start')).length===2,'only two explicit Starts');
// Changing a selector invalidates both successful and failed pending context.
hold='/'+ 'a'.repeat(32);entered=false;change('auto-run','a'.repeat(32));await until(()=>entered,'status held');change('workspace','');await until(settled,'emptyworkspace');lose='/'+ 'a'.repeat(32);released();await new Promise(r=>setTimeout(r,30));assert($('message').textContent==='Choose a workspace.'&&$('automation').hidden,'late failure cannot resurrect or overwrite context');
await workspace();available=false;$('refresh').click();await until(()=>settled()&&$('workspace').options.length===2,'refresh session');change('workspace','__WORKSPACE__');await until(()=>settled()&&$('auto-capabilities').textContent.includes('unavailable'),'disabled runtime');assert($('auto-start').disabled&&$('auto-policy').options.length===1,'unavailable policy cannot be manufactured');change('auto-run','a'.repeat(32));await until(()=>settled()&&!$('auto-stop').disabled,'Stop remains available without runtime');// A changed CSRF/session cookie while status is in flight clears all prior authority.
hold='/'+ 'a'.repeat(32);entered=false;change('auto-run','a'.repeat(32));await until(()=>entered,'session-bound status held');document.cookie='__Host-inlet_csrf='+'X'.repeat(43)+'; Path=/; Secure; SameSite=Strict';released();await until(()=>settled()&&$('selection').hidden,'changed session cookie clears context');assert($('automation').hidden&&!$('auto-status').textContent,'no stale status after session replacement');assert((await native('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'optimization-owner:replacement'})})).ok,'replacement actual session');$('refresh').click();await until(()=>settled()&&!$('selection').hidden,'replacement session loaded');change('workspace','__WORKSPACE__');await until(()=>settled()&&!$('automation').hidden,'replacement workspace');change('auto-run','a'.repeat(32));await until(()=>settled()&&!$('auto-stop').disabled,'owned old run recovery with fresh session');denied=true;$('auto-stop').click();await until(()=>settled()&&$('selection').hidden,'owner denial clears shell');assert($('automation').hidden&&!$('auto-status').textContent,'owner denial clears automation data');denied=false;$('refresh').click();await until(()=>settled()&&!$('selection').hidden,'new session read');$('logout').click();await until(()=>$('message').textContent==='Signed out.','logout');assert($('automation').hidden&&!$('auto-status').textContent,'logout clears automation state');
await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(e){await native('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:e.message,stack:e.stack})});}
