const browserFetch = globalThis.fetch;
// Local browser fixture: no external provider, database, or advertising traffic.
const calls = [];
const goalId = 'g'.repeat(32), storeId = 's'.repeat(32);
let goals = [], creates = 0;
Object.defineProperty(document, 'cookie', {get: () => '__Host-inlet_csrf=' + 'a'.repeat(43)});
globalThis.fetch = async (path, options) => {
  calls.push({path, options});
  const body = options.body ? JSON.parse(options.body) : null;
  if (options.method !== 'GET' && options.headers['X-CSRF-Token'] !== 'a'.repeat(43)) throw Error('CSRF missing');
  let value = [];
  if (path.endsWith('/session')) value = {email:'fixture@example.test'};
  else if (path.endsWith('/workspaces')) {
    if (options.method === 'POST') { creates++; value = {id:1,name:'Fixture',role:'owner'}; }
    else value = [{id:1,name:'<img src=x onerror=alert(1)>',role:'owner'}];
  } else if (path.endsWith('/commerce/stores')) value = [{id:storeId,status:'active',currency:'USD',time_zone:'America/New_York'}];
  else if (path.endsWith('/billing')) value = {status:'unconfigured',mode:'unavailable'};
  else if (path.endsWith('/preview')) value = {preview_id:'p'.repeat(32),snapshot_id:'b'.repeat(32),revision:goals[0].revision};
  else if (path.includes('/commerce/snapshots/')) value = {quality:'complete',total_micros:1000000};
  else if (path.endsWith('/confirm')) { goals[0].confirmation_recorded = true; value = goals[0]; }
  else if (path.endsWith('/goals') && options.method === 'POST') { value = {id:goalId,revision:1,definition:body.definition,assessment:'draft',confirmation_recorded:false}; goals = [value]; }
  else if (path.endsWith('/goals')) value = goals;
  else if (path.endsWith('/goals/' + goalId)) { goals[0] = {...goals[0],definition:body.definition,revision:2}; value = goals[0]; }
  return {ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(value))};
};
const $ = id => document.getElementById(id);
const wait = async () => { for (let i=0;i<30;i++) await new Promise(resolve=>setTimeout(resolve,0)); };
const assert = (truth, message) => { if (!truth) throw Error(message); };
async function run() {
try {
  await import('/app/assets/portal.mjs'); await wait();
  assert(!$('application').hidden,'Authenticated shell');
  assert(document.querySelectorAll('img').length === 0,'Escaped workspace name');
  $('provision').elements.namedItem('name').value = 'Fixture';
  $('provision').elements.namedItem('slug').value = 'fixture';
  $('provision').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  assert(creates === 1,'Workspace created');
  $('workspace').value = '1'; $('workspace').dispatchEvent(new Event('change')); await wait();
  assert(!$('workspace-content').hidden,'Workspace visible');
  assert($('checkout').hidden,'Unavailable checkout hidden');
  const values = {target:'10000',target_month:'2027-01',baseline_month:'2026-01',budget:'100',budget_start:'2027-01-01',budget_end:'2027-02-01'};
  for (const [name,value] of Object.entries(values)) $('goal-form').elements.namedItem(name).value = value;
  $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  assert(goals.length === 1 && goals[0].definition.store_id === storeId,'Saved scoped goal');
  assert(goals[0].definition.budget_micros === 100000000,'Exact budget');
  $('preview').click(); await wait(); assert(!$('review').hidden,'Baseline review visible');
  $('goal-form').elements.namedItem('target').value = '11000'; $('goal-form').dispatchEvent(new Event('input',{bubbles:true}));
  assert($('review').hidden && $('preview').hidden,'Editing invalidates reviewed revision');
  $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  $('preview').click(); await wait(); $('confirm').click(); await wait();
  assert(goals[0].confirmation_recorded,'Confirmed reviewed goal');
  const confirmation = calls.find(c=>c.path.endsWith('/confirm'));
  assert(JSON.parse(confirmation.options.body).expected_revision === 2,'Exact current revision confirmed');
  assert(!calls.some(c=>c.path.includes('/authorize') || c.path.includes('/dispatch') || c.path.includes('/checkout')),'No provider or ad actions');
  goals[0].definition.target_window.time_basis = 'cumulative';
  $('workspace').dispatchEvent(new Event('change')); await wait();
  $('goal').value = goalId; $('goal').dispatchEvent(new Event('change'));
  assert($('goal-form').hidden && !$('goal-limits').hidden,'Unsupported cumulative definition cannot be silently rewritten');
  $('logout').click(); await wait(); assert($('application').hidden,'Signout clears application');
  document.body.dataset.testResult = 'passed';
  await browserFetch('/__result__', {method:'POST',body:'passed'});
} catch (error) { document.body.dataset.testResult = 'failed'; document.body.append(document.createTextNode(error.stack)); await browserFetch('/__result__',{method:'POST',body:error.stack}); }

}
run();
