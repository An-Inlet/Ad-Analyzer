const mode='__MODE__',$=id=>document.getElementById('planning-'+id),assert=(v,m)=>{if(!v)throw Error(m);},nativeFetch=window.fetch,none={advertising_writes_enabled:false,spending_authority:'none'},calls=[];
let delayed=false,release=null,legacy=false;
const wait=async(predicate,label)=>{const end=Date.now()+3000;while(Date.now()<end){if(predicate())return;await new Promise(r=>setTimeout(r,10));}throw Error(label+': '+$('message').textContent);};
window.fetch=async(url,init={})=>{
 const path=String(url);calls.push({path,method:init.method??'GET'});let value;
 if(path==='/api/customer/v1/session')value={user_id:'alice'};
 else if(path==='/api/customer/v1/workspaces')value=[{id:1,name:'One',role:'owner'},{id:2,name:'Two',role:'owner'}];
 else if(path.endsWith('/goals'))value=[];
 else if(path.endsWith('/planning/accounts'))value={complete:true,accounts:[{id:2,name:'Google',platform:'google_ads'}]};
 else if(path.endsWith('/capabilities')){if(delayed)await new Promise(resolve=>{release=resolve;});const version=legacy?3:4;value={schema_version:'inlet.planning-capabilities.v1',workspace_id:1,policy_version:`inlet.descriptive-review.v${version}`,generator_version:`inlet.descriptive-planning.v${version}`,selected_reporting_available:!legacy,...none};}
 else if(path.endsWith('/plans?limit=20'))value={items:[{plan_id:'b'.repeat(32),version:0,input_revision:1,...none}],next_cursor:null};
 else if(path.endsWith('/plans/'+'b'.repeat(32)))return new Response('{}',{status:404});
 else throw Error('Unexpected request '+path);
 return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
};
const settled=()=>!$('list-refresh').disabled,choose=async(value)=>{$('workspace').value=value;$('workspace').dispatchEvent(new Event('change'));await wait(settled,'workspace settled');};
const editor=async()=>{$('new').click();await wait(()=>settled()&&!$('editor').hidden,'editor');};
try{
 await import('/app/assets/planning.mjs');await wait(()=>settled()&&!$('selection').hidden,'session');assert(location.hash==='','fragment consumed');await choose('1');await editor();assert(!$('capture-handoff').hidden,'pending hint');const field=$('selected-captures').querySelector('input');$('accounts').querySelector('input').checked=true;
 if(['workspace','session'].includes(mode)){
  delayed=true;$('apply-capture').click();await wait(()=>release!==null,'apply waiting for capability');
  if(mode==='workspace'){$('workspace').value='2';$('workspace').dispatchEvent(new Event('change'));}
  else{document.cookie='fixture_session=replaced; Path=/';window.dispatchEvent(new Event('focus'));}
  delayed=false;release();await wait(()=>$('editor').hidden,'stale editor cleared');await new Promise(r=>setTimeout(r,30));assert(field.value==='','late response cannot fill detached field');
  if(mode==='session'){$('refresh').click();await wait(()=>settled()&&!$('selection').hidden,'replacement session');}
  else await wait(settled,'new workspace read');
  await choose('1');await editor();assert($('capture-handoff').hidden&&$('selected-captures').querySelector('input').value==='','revoked hint cannot revive');
 }else if(mode==='cancel'){$('cancel').click();await editor();assert($('capture-handoff').hidden,'cancel revokes');}
 else if(mode==='saved'){$('plans').querySelector('button').click();await wait(()=>settled()&&$('editor').hidden,'saved selection');await editor();assert($('capture-handoff').hidden,'saved selection revokes');}
 else{legacy=true;$('apply-capture').click();await wait(()=>settled()&&$('capture-handoff').hidden,'legacy refusal');assert(field.value==='','unsupported capability cannot apply');}
 assert(calls.every(c=>c.method==='GET'),'revocation never saves or generates');await nativeFetch('/result',{method:'POST',body:'PASS'});
}catch(error){await nativeFetch('/result',{method:'POST',body:error.stack||String(error)});}finally{window.fetch=nativeFetch;}
