// Actual customer JSON, actual mocked provider reports and actual calculation.
const $=id=>document.getElementById('rf-'+id),assert=(ok,msg)=>{if(!ok)throw Error(msg);};
const until=async(fn,message)=>{const end=Date.now()+25000;while(!await fn()){if(Date.now()>end)throw Error(message+' · '+$('message').textContent);await new Promise(r=>setTimeout(r,20));}};
const settled=()=>!$('refresh').disabled;
const change=(id,value,event='change')=>{$(id).value=value;$(id).dispatchEvent(new Event(event));};
try{
assert((await fetch('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'reported-browser:actual'})})).ok,'actual sign in');
await import('/app/assets/reported-comparison.mjs');
await until(()=>settled()&&$('workspace').options.length===2,'workspace');change('workspace','__WORKSPACE__');
await until(()=>settled()&&$('action').options.length===2,'actual owned action');
change('action',$('action').options[1].value);change('cpa','100','input');$('request').click();
await until(()=>settled()&&$('progress').textContent.includes('pending'),'actual request');
const acquisition=await fetch('/__fixture__/acquire',{method:'POST'});assert(acquisition.ok,'actual acquisition and baseline '+await acquisition.text());
$('refresh').click();await until(()=>settled()&&$('workspace').options.length===2,'refresh');change('workspace','__WORKSPACE__');await until(()=>settled()&&$('baseline').options.length===2,'real calibrated baseline');
change('history',$('history').options[1].value);$('status').click();
await until(()=>settled()&&!$('comparison').hidden,'real comparison');
assert($('summary').textContent.includes('operational reported as of'),'comparison is actual operational report');
assert($('before').textContent.includes('USD 5')&&$('after').textContent.includes('USD 2.5'),'actual before/after CPAs');
change('baseline',$('baseline').options[1].value);$('apply').click();
await until(()=>settled()&&!$('result').hidden,'real changed preview');
assert($('preview').textContent.includes('USD 47'),'computed47 from46 baseline');
assert($('explanation').textContent.includes('do not compound'),'no compounding claim');
assert(document.body.textContent.includes('Review handoff is unavailable'),'no financial handoff');
// Hold the real response, not substitute a result; a changed workspace must clear it.
const original=globalThis.fetch.bind(globalThis);let entered=false,release;
globalThis.fetch=async(url,init)=>{const response=await original(url,init);if(String(url).endsWith('/reported-feedback/previews')&&init?.method==='POST'){entered=true;await new Promise(r=>{release=r;});}return response;};
$('apply').click();await until(()=>entered,'actual repeated response held');change('workspace','');release();await new Promise(r=>setTimeout(r,100));
assert($('result').hidden&&!$('preview').textContent,'late actual response discarded');globalThis.fetch=original;
change('workspace','__WORKSPACE__');await until(()=>settled()&&$('history').options.length===2,'restore original session history');change('history',$('history').options[1].value);$('status').click();await until(()=>settled()&&!$('comparison').hidden,'restore comparison');change('baseline',$('baseline').options[1].value);
entered=false;globalThis.fetch=async(url,init)=>{const response=await original(url,init);if(String(url).endsWith('/reported-feedback/previews')&&init?.method==='POST'){entered=true;await new Promise(r=>{release=r;});}return response;};
$('apply').click();await until(()=>entered,'hold response before actual session rotation');
assert((await original('/api/customer/v1/session',{method:'POST',headers:{'Content-Type':'application/json','X-Inlet-Request':'1'},body:JSON.stringify({id_token:'reported-browser:rotated'})})).ok,'rotate original session');release();await until(()=>settled()&&$('selection').hidden,'changed session invalidates result');assert($('result').hidden&&!$('preview').textContent,'old-session response never restores values');globalThis.fetch=original;
$('refresh').click();await until(()=>settled()&&!$('logout').hidden,'fresh session refresh');
$('logout').click();await until(()=>$('message').textContent==='Signed out.','actual logout');assert($('selection').hidden,'session clears all values');
await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'passed'})});
}catch(error){await fetch('/__fixture__/result',{method:'POST',body:JSON.stringify({status:'failed',message:error.message,stack:error.stack})});}
