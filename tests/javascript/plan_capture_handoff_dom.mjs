import {captureHandoff,parseCaptureHint,captureHintPath} from './plan-capture-handoff.mjs';
import {renderSelectedCaptures,clearSelectedCaptures} from './plan-selected-captures.mjs';
const assert=(v,m)=>{if(!v)throw Error(m);},rejects=(fn,m)=>{let failed=false;try{fn();}catch{failed=true;}assert(failed,m);};
const id='a'.repeat(32),fragment=`#inlet-capture-v1=1:2:${id}`,cookies='opaque-fixture',owner=[{id:1,role:'owner'}],hint=parseCaptureHint(fragment);
const cap={schema_version:'inlet.planning-capabilities.v1',workspace_id:1,policy_version:'inlet.descriptive-review.v4',generator_version:'inlet.descriptive-planning.v4',selected_reporting_available:true,advertising_writes_enabled:false,spending_authority:'none'};
const host=document.querySelector('#host'),options={capability:cap,workspaceId:1,accounts:[{id:2,name:'<img src=x>',platform:'google_ads'}]};
try{
 assert(captureHintPath(1,2,id)==='/app/planning'+fragment,'exact navigation');
 for(const bad of ['',fragment+'&capture=x',fragment+fragment,fragment.replace('1:2','01:2'),fragment.replace('1:2','9007199254740992:2'),fragment.replace(id,id.toUpperCase()),fragment.replace(':','%3A'),fragment.replace('1:2','1:0')])assert(parseCaptureHint(bad)===null,'malformed rejected');
 rejects(()=>captureHintPath(0,2,id),'bad source scope');
 let state=captureHandoff(fragment,cookies);assert(state.offered(1,cookies)===null,'unbound');state.bind(owner,cookies);assert(state.offered(1,cookies)===null,'unselected');state.choose(1,cookies);assert(state.offered(1,cookies)?.captureId===id,'explicit chosen workspace');state.choose(1,cookies);assert(state.offered(1,cookies)===null,'workspace reselection revokes');
 for(const [workspaces,selectedCookie,workspace] of [[[{id:2,role:'owner'}],cookies,1],[[{id:1,role:'viewer'}],cookies,1],[owner,'replaced',1],[owner,cookies,2]]){state=captureHandoff(fragment,cookies);state.bind(workspaces,cookies);state.choose(workspace,selectedCookie);assert(state.offered(1,cookies)===null,'foreign scope/session rejected');}
 state=captureHandoff(fragment,cookies);state.bind(owner,cookies);state.choose(1,cookies);assert(state.offered(1,'replaced')===null&&state.offered(1,cookies)===null,'replacement irrevocable');
 state=captureHandoff(fragment,cookies);state.bind(owner,cookies);state.choose(1,cookies);state.revoke();assert(state.offered(1,cookies)===null,'explicit revocation');
 let handle=renderSelectedCaptures(host,options);rejects(()=>handle.applyHint(hint,[]),'unchecked account');rejects(()=>handle.applyHint({...hint,workspaceId:2},[2]),'foreign workspace');rejects(()=>handle.applyHint({...hint,accountId:3},[3]),'foreign account');handle.applyHint(hint,[2]);assert(host.querySelector('input').value===id&&!host.querySelector('img'),'literal exact applied');rejects(()=>handle.applyHint({...hint,captureId:'b'.repeat(32)},[2]),'no overwrite');clearSelectedCaptures(host);rejects(()=>handle.applyHint(hint,[2]),'stale handle');
 handle=renderSelectedCaptures(host,{...options,saved:[]});rejects(()=>handle.applyHint(hint,[2]),'no existing plan edits');handle=renderSelectedCaptures(host,{...options,accounts:[{id:2,name:'Meta',platform:'meta_ads'}]});rejects(()=>handle.applyHint(hint,[2]),'unsupported account');
 handle=renderSelectedCaptures(host,{...options,capability:{...cap,policy_version:'inlet.descriptive-review.v3',generator_version:'inlet.descriptive-planning.v3',selected_reporting_available:false}});assert(!handle.applyHint&&handle.readIntent([2])===undefined,'legacy unchanged');
 await fetch('/result',{method:'POST',body:'PASS'});
}catch(error){await fetch('/result',{method:'POST',body:error.stack||String(error)});}
