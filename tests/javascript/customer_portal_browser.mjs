const browserFetch = globalThis.fetch;
// Local browser fixture: no external provider, database, or advertising traffic.
const calls = [];
const goalId = 'g'.repeat(32), storeId = 's'.repeat(32);
let goals = [], creates = 0, principal = 'A', failWorkspaces = false, loseGoal = true;
let releaseGoals = null, deferGoals = false, unauthorized = false, rejectCreate = false, lossStatus = null;
const receipts = new Map();
Object.defineProperty(document, 'cookie', {get: () => '__Host-inlet_csrf=' + 'a'.repeat(43)});
globalThis.fetch = async (path, options) => {
  calls.push({path, options});
  const body = options.body ? JSON.parse(options.body) : null;
  if (unauthorized && path.endsWith('/billing')) return {ok:false,status:401};
  if (options.method !== 'GET' && options.headers['X-CSRF-Token'] !== 'a'.repeat(43)) throw Error('CSRF missing');
  let value = [];
  if (path.endsWith('/session')) value = {email:'fixture@example.test'};
  else if (path.endsWith('/workspaces')) {
    if (options.method === 'POST') { creates++; value = {id:1,name:'Fixture',role:'owner'}; }
    else if (failWorkspaces) throw Error('Workspace load failed');
    else if (principal === 'B') value = [];
    else value = [{id:1,name:'<img src=x onerror=alert(1)>',role:'owner'}];
  } else if (path.endsWith('/commerce/stores')) value = [{id:storeId,status:'active',currency:'USD',time_zone:'America/New_York'}];
  else if (path.endsWith('/billing')) value = {status:'unconfigured',mode:'unavailable'};
  else if (path.endsWith('/preview')) value = {preview_id:'p'.repeat(32),snapshot_id:'b'.repeat(32),revision:goals[0].revision};
  else if (path.includes('/commerce/snapshots/')) value = {quality:'complete',net_sales_micros:1000000000,currency:'USD',orders:10,window:{start:'2026-01-01',end:'2026-02-01',time_basis:'calendar_month'},reasons:[]};
  else if (path.endsWith('/confirm')) { goals[0].confirmation_recorded = true; value = goals[0]; }
  else if (path.endsWith('/goals') && options.method === 'POST') {
    if (rejectCreate) { rejectCreate = false; return {ok:false,status:422}; }
    const key = options.headers['Idempotency-Key'];
    assert(Boolean(key), 'Creation key present');
    if (!receipts.has(key)) { value = {id:receipts.size ? String(receipts.size).repeat(32) : goalId,revision:1,definition:body.definition,assessment:'draft',confirmation_recorded:false}; receipts.set(key, value); goals.push(value); }
    value = receipts.get(key);
    if (loseGoal) { loseGoal = false; if (lossStatus) return {ok:false,status:lossStatus}; throw Error('Response lost after commit'); }
  }
  else if (path.endsWith('/goals')) { if (deferGoals) await new Promise(resolve => { releaseGoals = resolve; }); value = goals; }
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
  assert($('message').textContent.includes('Response lost'), 'Committed response lost');
  $('goal-form').elements.namedItem('target').value = '12000';
  $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  assert($('message').textContent.includes('unknown outcome') && receipts.size === 1, 'Changed input cannot rotate uncertain key');
  $('goal-form').elements.namedItem('target').value = '10000';
  $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  assert(receipts.size === 1, 'Retry reuses creation key');
  assert(goals.length === 1 && goals[0].definition.store_id === storeId,'Saved scoped goal');
  assert(goals[0].definition.budget_micros === 100000000,'Exact budget');
  $('preview').click(); await wait(); assert(!$('review').hidden,'Baseline review visible');
  for (const expected of ['Target Sales','USD 10,000.00','January 2027','Total Budget','USD 100.00','Historical Baseline','Ready To Review','USD 1,000.00','January 2026']) assert($('review-data').textContent.replace(/\s/g, ' ').includes(expected), 'Readable review: ' + expected);
  assert(!$('review-data').textContent.includes('net_sales_micros') && !$('review-data').textContent.includes(storeId),'No implementation fields in review');
  assert($('connections').textContent.includes('Not Connected'),'Readable connection status');
  assert($('goal-detail').textContent.includes('Current sales progress is not available'),'Unknown progress explicit');
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
  const fill = target => { for (const [name,value] of Object.entries({...values, target})) $('goal-form').elements.namedItem(name).value = value; };
  $('goal').value = ''; $('goal').onchange(); fill('12000'); loseGoal = true; lossStatus = 503;
  $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  assert(receipts.size === 2, 'Second goal committed before lost response');
  goals[0].definition.target_window.time_basis = 'calendar_month';
  $('goal').value = goalId; $('goal').onchange(); fill('13000');
  $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  $('goal').value = ''; $('goal').onchange(); fill('12000');
  $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  assert(receipts.size === 2 && goals.length === 2, 'Editing another goal preserves uncertain creation receipt');
  $('goal').value = ''; $('goal').onchange(); fill('14000'); rejectCreate = true;
  $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  assert($('message').textContent.includes('Check the entered values'), 'Definite rejection shown');
  fill('15000'); $('goal-form').dispatchEvent(new Event('submit',{cancelable:true})); await wait();
  assert(receipts.size === 3 && goals.length === 3, 'Corrected input allowed after definite rejection');
  $('logout').click(); await wait(); assert($('application').hidden,'Signout clears application');
  assert($('goal-detail').textContent === '' && $('billing').textContent === '' && $('workspace-content').hidden, 'Signout erases customer data');
  principal = 'B'; $('retry').click(); await wait();
  assert(!$('application').hidden && $('workspace-content').hidden, 'New customer without workspaces sees no previous content');
  assert($('goal').options.length === 0 && $('store').options.length === 0, 'Customer selections erased');
  principal = 'A'; $('retry').click(); await wait();
  $('workspace').value = '1'; $('workspace').dispatchEvent(new Event('change')); await wait();
  assert(!$('workspace-content').hidden, 'Original customer reloads independently');
  failWorkspaces = true; $('retry').click(); await wait();
  assert($('application').hidden && $('billing').textContent === '' && $('goal-detail').textContent === '', 'Failed session refresh cannot retain customer data');
  failWorkspaces = false; $('retry').click(); await wait();
  deferGoals = true; $('workspace').value = '1'; $('workspace').dispatchEvent(new Event('change')); await wait();
  assert(releaseGoals !== null, 'Old customer fetch pending');
  principal = 'B'; $('retry').onclick(); await wait();
  releaseGoals(); await wait();
  assert($('workspace-content').hidden && $('billing').textContent === '' && $('goal').options.length === 0, 'Late old-customer response cannot repopulate new session');
  deferGoals = false; principal = 'A'; $('retry').onclick(); await wait();
  unauthorized = true; $('workspace').value = '1'; $('workspace').onchange(); await wait();
  assert($('application').hidden && $('goal-detail').textContent === '' && $('workspace').options.length === 0, '401 clears entire customer state');
  document.body.dataset.testResult = 'passed';
  await browserFetch('/__result__', {method:'POST',body:'passed'});
} catch (error) { document.body.dataset.testResult = 'failed'; document.body.append(document.createTextNode(error.stack)); await browserFetch('/__result__',{method:'POST',body:error.stack}); }

}
run();
