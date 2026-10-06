const network = fetch, $ = id => document.getElementById(id);
const assert = (ok, message) => { if (!ok) throw Error(message); };
const until = async test => { for(let i=0;i<300;i++) { if(test()) return; await new Promise(r=>setTimeout(r,10)); } throw Error('Condition did not settle'); };
let identity = 'one', revoked = false, hold = false, release, reject, holdJson = false, rejectJson;
const row = wid => ({schema_version:'inlet.customer.activity.v1',workspace_id:wid,items:[{source:'goal',event:'confirmed',revision:wid,recorded_at:'2026-10-06T00:00:00Z'}],truncated:false,receipt_coverage:'owner_only',receipt_unavailable:0});
globalThis.fetch = async (path, options) => {
  assert(options.credentials === 'same-origin' && options.cache === 'no-store', 'Private request contract');
  if (revoked) return {ok:false,status:401};
  let value;
  if(path.endsWith('/session')) value = {user_id:identity};
  else if(path.endsWith('/workspaces')) value = [{id:1,name:'First'},{id:2,name:'<script>unsafe</script>'}];
  else if(path.endsWith('/activity')) {
    const wid = Number(path.split('/').at(-2));
    if (hold) { hold=false; await new Promise((resolve, failure)=>{release=resolve;reject=failure;}); }
    value=row(wid);
  } else throw Error('Unexpected endpoint');
  return {ok:true,status:200,json:async()=>{ if(path.endsWith('/activity') && holdJson) { holdJson=false; await new Promise((resolve, failure)=>{rejectJson=failure;}); } return value; }};
};
try {
  await import('/app/assets/activity.mjs');
  await until(()=>$('activity-workspace').options.length === 3);
  assert(!$('activity-workspace').querySelector('script'), 'Workspace name treated as text');
  const choose = wid => { $('activity-workspace').value=String(wid); $('activity-workspace').dispatchEvent(new Event('change')); };
  choose(1); await until(()=>$('activity-items').textContent.includes('Revision 1'));
  assert($('activity-coverage').textContent.includes('only to the workspace owner'), 'Owner restriction visible');
  hold=true; $('activity-refresh').click(); await until(()=>Boolean(release));
  assert(!$('activity-items').textContent, 'Old private history cleared during refresh');
  choose(2); await until(()=>$('activity-items').textContent.includes('Revision 2'));
  release(); await new Promise(r=>setTimeout(r,50));
  assert(!$('activity-items').textContent.includes('Revision 1'), 'Late workspace response ignored');
  release=null; hold=true; choose(1); await until(()=>Boolean(release));
  choose(2); await until(()=>$('activity-items').textContent.includes('Revision 2'));
  reject(Error('Old request failed')); await new Promise(r=>setTimeout(r,50));
  assert($('activity-items').textContent.includes('Revision 2'), 'Old network failure cannot clear current history');
  holdJson=true; choose(1); await until(()=>Boolean(rejectJson));
  choose(2); await until(()=>$('activity-items').textContent.includes('Revision 2'));
  rejectJson(Error('Old body failed')); await new Promise(r=>setTimeout(r,50));
  assert($('activity-items').textContent.includes('Revision 2'), 'Old body failure cannot clear current history');
  identity='two'; $('activity-refresh').click();
  await until(()=>$('activity-controls').hidden);
  assert(!$('activity-items').textContent, 'Account switch clears history');
  $('activity-session').click(); await until(()=>$('activity-workspace').options.length===3);
  choose(1); await until(()=>$('activity-items').textContent.includes('Revision 1'));
  revoked=true; $('activity-refresh').click(); await until(()=>$('activity-controls').hidden);
  assert(!$('activity-items').textContent, 'Revoked session clears history');
  await network('/__result__',{method:'POST',body:'passed'});
} catch(error) { await network('/__result__',{method:'POST',body:String(error.stack || error)}); }
