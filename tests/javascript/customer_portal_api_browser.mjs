// Real HTTPS fetch, real application cookies, real API/database; only SDK is a fixture.
const $ = id => document.getElementById(id);
const assert = (value, message) => { if (!value) throw Error(message); };
async function until(predicate, message) {
  const deadline = Date.now() + 15000;
  while (!predicate()) {
    if (Date.now() > deadline) throw Error(message);
    await new Promise(resolve => setTimeout(resolve, 20));
  }
}
async function api(path, method = 'GET', body, extra = {}) {
  const headers = {...extra};
  if (method !== 'GET' && path.startsWith('/api/customer/')) {
    headers['X-CSRF-Token'] = document.cookie.split(';').map(x => x.trim()).find(x => x.startsWith('__Host-inlet_csrf='))?.split('=')[1];
  }
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  return fetch(path, {method, headers, body:body === undefined ? undefined : JSON.stringify(body), credentials:'same-origin'});
}
async function run() {
  await until(() => $('signin') && !$('signin').hidden && !$('signin').disabled, 'Sign-in unavailable');
  $('signin').click();
  await until(() => $('message').textContent.includes('outcome could not be confirmed'), 'Interrupted sign-in not reported');
  assert($('application').hidden, 'Unknown sign-in outcome must hide application');
  $('retry').click();
  await until(() => !$('application').hidden && !$('retry').disabled, 'Existing committed session not recovered');
  assert(!document.cookie.includes('__Host-inlet_session='), 'Session cookie must remain HttpOnly');
  assert(document.cookie.includes('__Host-inlet_csrf='), 'Actual secure CSRF cookie installed');
  $('provision').elements.namedItem('name').value = 'Browser Journey';
  $('provision').elements.namedItem('slug').value = 'browser-journey';
  $('provision').dispatchEvent(new Event('submit', {cancelable:true}));
  await until(() => $('message').className === 'error' && !$('retry').disabled, 'Lost workspace response not reported');
  $('provision').dispatchEvent(new Event('submit', {cancelable:true}));
  await until(() => !$('workspace-content').hidden && !$('retry').disabled, 'Workspace retry failed');
  const wid = $('workspace').value, root = `/api/customer/v1/workspaces/${wid}`;
  const workspaces = await (await api('/api/customer/v1/workspaces')).json();
  assert(workspaces.length === 1 && workspaces[0].role === 'owner', 'Workspace retry must replay one owner membership');
  const values = {target:'10000',target_month:'2026-11',baseline_month:'2026-09',budget:'100',budget_start:'2026-11-01',budget_end:'2026-12-01'};
  for (const [name,value] of Object.entries(values)) $('goal-form').elements.namedItem(name).value = value;
  $('goal-form').dispatchEvent(new Event('submit', {cancelable:true}));
  await until(() => $('message').className === 'error' && !$('retry').disabled, 'Lost goal response not reported');
  $('goal-form').dispatchEvent(new Event('submit', {cancelable:true}));
  await until(() => $('message').textContent.includes('Goal draft saved') && !$('retry').disabled, 'Goal retry failed');
  const goals = await (await api(root + '/goals')).json();
  assert(goals.length === 1, 'Goal retry must replay one persisted goal');
  $('preview').click();
  await until(() => !$('review').hidden && !$('confirm').disabled, 'Actual baseline not reviewed');
  assert($('review-data').textContent.replace(/\s/g, ' ').includes('USD 90.00'), 'Canonical database baseline displayed');
  $('confirm').click();
  await until(() => $('message').textContent.includes('Goal confirmed') && !$('retry').disabled, 'Goal confirmation failed');
  const checkout = await api(root + '/billing/checkout', 'POST');
  assert(checkout.ok && (await checkout.json()).mode === 'fixture', 'Actual checkout endpoint returns explicit fixture result');
  const event = await (await fetch('/__fixture__/billing-event')).json();
  const webhook = await fetch('/api/billing/stripe/events', {method:'POST', headers:{'Stripe-Signature':event.signature}, body:event.body});
  assert(webhook.ok, 'Actual signed billing webhook failed');
  const reconcile = await fetch('/__fixture__/billing-run', {method:'POST'});
  assert(reconcile.ok, 'Real billing dispatcher failed');
  $('workspace').dispatchEvent(new Event('change'));
  await until(() => $('billing').textContent.startsWith('Active') && !$('retry').disabled, 'Canonical billing status not rendered');
  $('logout').click();
  await until(() => $('application').hidden && !$('retry').disabled, 'Logout failed');
  assert((await api('/api/customer/v1/session')).status === 401, 'Real session revoked');
  globalThis.__fixtureIdentity = 'browser-b';
  $('signin').click();
  await until(() => !$('application').hidden && !$('retry').disabled, 'Second customer sign-in failed');
  assert($('workspace-content').hidden && $('billing').textContent === '' && $('goal-detail').textContent === '', 'Second customer cannot see prior state');
  assert((await api(root + '/goals')).status === 404, 'Second customer cannot access first customer goal');
  document.body.dataset.apiJourney = 'passed';
  return {status:'passed', workspace_id:Number(wid), goal_id:goals[0].id};
}
run().then(result => fetch('/__fixture__/result', {method:'POST',body:JSON.stringify(result)})).catch(error => fetch('/__fixture__/result', {method:'POST',body:JSON.stringify({status:'failed', message:error.stack})}));
