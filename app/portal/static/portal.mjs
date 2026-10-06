export function micros(value) {
  if (!/^\d+(\.\d{1,2})?$/.test(value)) throw new Error('Enter an amount with up to two decimal places.');
  const [whole, fraction = ''] = value.split('.');
  const result = Number(whole) * 1000000 + Number(fraction.padEnd(2, '0')) * 10000;
  if (!Number.isSafeInteger(result) || result > 1e15) throw new Error('Amount is too large.');
  return result;
}
export function monthWindow(value, store) {
  if (!/^\d{4}-\d{2}$/.test(value)) throw new Error('Choose a calendar month.');
  const [year, month] = value.split('-').map(Number);
  if (year < 1900 || year > 9998 || month < 1 || month > 12) throw new Error('Invalid calendar month.');
  const end = `${month === 12 ? year + 1 : year}-${String(month === 12 ? 1 : month + 1).padStart(2, '0')}-01`;
  return {start: `${value}-01`, end, time_basis: 'calendar_month', currency: store.currency, time_zone: store.time_zone};
}
export function definitionFrom(values, store) {
  if (!store) throw new Error('A connected Shopify store is required.');
  const target = monthWindow(values.target_month, store);
  return {metric: 'shopify_merchandise_net_sales_v1', store_id: store.id,
    target_micros: micros(values.target), target_window: target,
    baseline_window: monthWindow(values.baseline_month, store),
    deadline: new Date(Date.parse(target.end + 'T00:00:00Z') - 86400000).toISOString().slice(0, 10),
    budget_micros: micros(values.budget), budget_start: values.budget_start, budget_end: values.budget_end,
    aggressiveness: values.aggressiveness};
}
export function billingDestination(result, kind) {
  // Fixture links never navigate. Only the explicitly configured test provider may redirect.
  if (result.mode !== 'stripe_test') throw new Error('Billing is unavailable outside configured test mode.');
  const url = new URL(result.url);
  const host = kind === 'checkout' ? 'checkout.stripe.com' : 'billing.stripe.com';
  if (url.protocol !== 'https:' || url.hostname !== host || url.port || url.username || url.password) throw new Error('Billing returned an invalid destination.');
  return url.href;
}
export function amount(value, currency) {
  if (!Number.isSafeInteger(value) || !/^[A-Z]{3}$/.test(currency || '')) return 'Not Available';
  return new Intl.NumberFormat('en-US', {style: 'currency', currency, currencyDisplay: 'code'}).format(value / 1e6);
}
export function period(window) {
  if (!window?.start || !window?.end) return 'Not Available';
  const start = new Date(window.start + 'T00:00:00Z');
  if (!Number.isFinite(start.getTime())) return 'Not Available';
  return window.time_basis === 'calendar_month' ? new Intl.DateTimeFormat('en-US', {month: 'long', year: 'numeric', timeZone: 'UTC'}).format(start) : `${window.start} to ${window.end} (end excluded)`;
}
const labels = {active: 'Active', connected: 'Connected', disconnected: 'Disconnected', pending: 'Pending', revoked: 'Revoked', draft: 'Draft', approved: 'Approved For Simulation', confirmed: 'Confirmed', baseline_unavailable: 'Baseline Needs Attention', unavailable: 'Unavailable', unconfigured: 'Not Configured', trialing: 'Trial', past_due: 'Payment Overdue', canceled: 'Canceled', unpaid: 'Unpaid', incomplete: 'Setup Incomplete', incomplete_expired: 'Setup Expired', paused: 'Paused', conservative: 'Conservative', balanced: 'Balanced', assertive: 'Assertive', google_ads: 'Google Ads', meta_ads: 'Meta Ads', tiktok_ads: 'TikTok Ads'};
const label = value => labels[value] || 'Status Unavailable';
export function baselineWarnings(reasons) {
  const descriptions = {missing_history: 'Historical data is missing for part or all of the selected baseline month. The source has not identified individual missing months.', incomplete_window: 'The selected baseline month has not been fully imported.', stale_source: 'The latest source data is too old to confirm this baseline.', import_in_progress: 'A source import is still in progress.', source_error: 'The source import needs attention.', unreconciled_source: 'Some source records have not reconciled.', outside_retention: 'The selected baseline is outside the retained history.'};
  return Array.isArray(reasons) ? reasons.map(reason => descriptions[reason] || 'Baseline data needs attention.') : [];
}
export function goalSummary(definition) {
  if (!definition) return [['Goal', 'No Goal Definition Yet']];
  const currency = definition.target_window?.currency;
  return [['Target Sales', amount(definition.target_micros, currency)], ['Target Period', period(definition.target_window)], ['Baseline Period', period(definition.baseline_window)], ['Store Time Zone', definition.target_window?.time_zone || 'Not Available'], ['Total Budget', amount(definition.budget_micros, currency)], ['Budget Period', `${definition.budget_start} to ${definition.budget_end} (end excluded)`], ['Aggressiveness', label(definition.aggressiveness)]];
}

export async function request(path, method = 'GET', body, headers = {}, fetcher = globalThis.fetch, cookies = globalThis.document?.cookie || '') {
  if (!path.startsWith('/api/customer/v1/') || path.includes('..')) throw new Error('Invalid request.');
  const csrf = cookies.split(';').map(v => v.trim()).find(v => v.startsWith('__Host-inlet_csrf='))?.split('=')[1];
  const outgoing = {'Accept': 'application/json', ...headers};
  if (method !== 'GET') {
    if (!csrf || !/^[A-Za-z0-9_-]{43}$/.test(csrf)) throw new Error('Your session needs to be refreshed.');
    outgoing['X-CSRF-Token'] = csrf;
    outgoing['Content-Type'] = 'application/json';
  }
  const response = await fetcher(path, {method, headers: outgoing, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin', redirect: 'error', cache: 'no-store'});
  if (!response.ok) {
    const error = new Error(({401: 'Your session has ended. Sign in again when customer sign-in is available.', 403: 'Your role or session does not permit this action.', 404: 'This item is unavailable in your workspace.', 409: 'The saved state changed or is not ready. Reload and review before trying again.', 422: 'Check the entered values and measurement periods.', 429: 'Usage limit reached. Try again later.', 502: 'The provider is temporarily unavailable.', 503: 'This service is not configured or is temporarily unavailable.'})[response.status] || 'The request could not be completed.');
    if (response.status === 409) {
      const payload = await response.json().catch(() => null);
      if (payload?.detail?.code === 'baseline_unavailable') {
        error.message = 'Baseline Not Ready. ' + baselineWarnings(payload.detail.reasons).join(' ');
      }
    }
    error.status = response.status;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

if (typeof document !== 'undefined') {
  const $ = id => document.getElementById(id);
  let workspaces = [], stores = [], goals = [], selectedGoal = null, reviewed = null, epoch = 0;
  let signupKey = null, signupBody = null;
  const root = () => `/api/customer/v1/workspaces/${encodeURIComponent($('workspace').value)}`;
  const say = (text, error = false) => { $('message').textContent = text; $('message').className = error ? 'error' : ''; };
  const show = (id, visible) => { $(id).hidden = !visible; };
  const textNode = (tag, text) => { const node = document.createElement(tag); node.textContent = text; return node; };
  function summary(container, rows) {
    const list = document.createElement('dl');
    for (const [name, value] of rows) list.append(textNode('dt', name), textNode('dd', value));
    container.append(list);
  }
  function renderConnections(entries) {
    $('connections').replaceChildren();
    const table = document.createElement('table');
    const head = document.createElement('tr');
    for (const title of ['Tool', 'Connection', 'Last Import', 'Attention']) { const cell = textNode('th', title); cell.scope = 'col'; head.append(cell); }
    table.append(head);
    for (const [name, connections] of entries) {
      const rows = Array.isArray(connections) && connections.length ? connections : [null];
      for (const [index, connection] of rows.entries()) {
        const row = document.createElement('tr');
        const state = connection ? label(connection.status) : Array.isArray(connections) ? 'Not Connected' : 'Status Unavailable';
        const imported = connection?.last_sync_at ? new Date(connection.last_sync_at).toLocaleString('en-US', {timeZone:'UTC'}) + ' UTC' : 'No Import Recorded';
        const attention = connection?.error_code ? 'Import Needs Attention' : connection?.live_verified === false ? 'Live Connection Not Verified' : connection ? 'No Reported Import Error' : 'Setup Not Available Here';
        for (const value of [name + (rows.length > 1 ? ` ${index + 1}` : ''), state, imported, attention]) row.append(textNode('td', value));
        table.append(row);
      }
    }
    $('connections').append(table);
  }
  function renderMandates(mandates) {
    $('mandates').replaceChildren();
    if (!mandates.length) { $('mandates').append(textNode('p', 'No mandates yet. Goal confirmation does not create a spending mandate.')); return; }
    for (const [index, mandate] of mandates.entries()) {
      const d = mandate.definition;
      $('mandates').append(textNode('h3', `Mandate ${index + 1} · Simulation`));
      summary($('mandates'), [['Status', mandate.paused ? 'Paused' : label(mandate.state)], ['Advertising Tools', [...new Set(d.accounts.map(a => label(a.platform)))].join(', ') || 'Not Available'], ['Total Spending Limit', amount(d.total_cap_micros, d.currency)], ['Per-Action Limit', amount(d.per_action_cap_micros, d.currency)], ['Simulated Spend Observed', amount(mandate.observed_simulated_micros, d.currency)], ['Simulated Amount Reserved', amount(mandate.reserved_simulated_micros, d.currency)], ['Actions Used', String(mandate.actions_used ?? 'Not Available')], ['Period', `${d.starts_at} to ${d.ends_at}`], ['Live Advertising', 'Disabled']]);
    }
  }
  const option = (value, label) => { const node = document.createElement('option'); node.value = value; node.textContent = label; return node; };
  const invalidate = () => { reviewed = null; show('review', false); };
  async function guarded(task) {
    const controls = [...document.querySelectorAll('button,input,select')];
    const states = controls.map(c => c.disabled);
    controls.forEach(c => { c.disabled = true; });
    try { await task(); } catch (error) {
      say(error.message, true);
      if (error.status === 401) { epoch++; show('application', false); show('signed-out', true); show('logout', false); }
    } finally { controls.forEach((c, i) => { c.disabled = states[i]; }); }
  }
  async function session() {
    try {
      await request('/api/customer/v1/session');
      workspaces = await request('/api/customer/v1/workspaces');
      $('workspace').replaceChildren(option('', 'Select A Workspace'), ...workspaces.map(w => option(w.id, `${w.name} · ${w.role}`)));
      show('application', true); show('signed-out', false); show('logout', true); say('Choose or create a workspace.');
    } catch (error) { show('application', false); show('signed-out', true); show('logout', false); say(error.message, true); }
  }
  function editGoal() {
    invalidate(); selectedGoal = goals.find(g => g.id === $('goal').value) || null;
    $('goal-form').reset();
    const d = selectedGoal?.definition;
    const editable = !d || (d.target_window.time_basis === 'calendar_month' && d.baseline_window.time_basis === 'calendar_month');
    show('goal-form', editable); show('goal-limits', !editable);
    if (d) {
      const values = {store_id: d.store_id, target: String(d.target_micros / 1e6), target_month: d.target_window.start.slice(0, 7), baseline_month: d.baseline_window.start.slice(0, 7), budget: String(d.budget_micros / 1e6), budget_start: d.budget_start, budget_end: d.budget_end, aggressiveness: d.aggressiveness};
      for (const [key, value] of Object.entries(values)) $('goal-form').elements.namedItem(key).value = value;
    }
    $('goal-detail').replaceChildren();
    if (selectedGoal) {
      summary($('goal-detail'), [['Goal Status', label(selectedGoal.assessment)], ...goalSummary(d)]);
      $('goal-detail').append(textNode('p', 'Current sales progress is not available in this view. A confirmed goal does not mean the sales target has been achieved.'));
      if (selectedGoal.assessment === 'baseline_unavailable') $('goal-detail').append(textNode('p', 'The baseline is no longer ready. Review again to check missing history, incomplete imports or stale data.'));
    } else $('goal-detail').append(textNode('p', 'Create an editable draft.'));
    show('preview', Boolean(selectedGoal?.definition)); updateBasis();
  }
  function updateBasis() { const store = stores.find(s => s.id === $('store').value); $('basis').textContent = store ? `Currency: ${store.currency} · Store Time Zone: ${store.time_zone}` : 'A Shopify store must be connected before a goal can be saved.'; }
  async function loadWorkspace() {
    const turn = ++epoch; invalidate(); selectedGoal = null; show('workspace-content', false);
    if (!$('workspace').value) return;
    const path = root();
    const result = await Promise.all([request(path + '/commerce/stores'), request(path + '/goals'), request(path + '/mandates'), request(path + '/billing')]);
    if (turn !== epoch) return;
    [stores, goals] = result;
    $('store').replaceChildren(...stores.filter(s => s.status === 'active').map((s, i) => option(s.id, `Shopify Store ${i + 1} · ${s.currency} · ${s.time_zone}`)));
    $('goal').replaceChildren(option('', 'New Goal'), ...goals.map((g, i) => option(g.id, `Goal ${i + 1} · ${period(g.definition?.target_window)} · ${g.confirmation_recorded ? 'Confirmed' : 'Draft'}`)));
    renderMandates(result[2]);
    const billing = result[3]; $('billing').textContent = `${label(billing.status)} · ${billing.mode === 'stripe_test' ? 'Test Billing Only' : 'Purchasing Unavailable'} · Live billing has not been verified.`;
    const owner = workspaces.find(w => String(w.id) === $('workspace').value)?.role === 'owner';
    show('checkout', owner && billing.mode === 'stripe_test'); show('management', owner && billing.mode === 'stripe_test');
    const providers = [['Google Ads', '/google/connections'], ['TikTok Ads', '/sources/tiktok_ads'], ['Klaviyo', '/sources/klaviyo'], ['HubSpot', '/sources/hubspot'], ['Omnisend', '/sources/omnisend']];
    const results = await Promise.all(providers.map(async ([name, endpoint]) => { try { return [name, await request(path + endpoint)]; } catch (error) { if (error.status === 401) throw error; return [name, 'Status unavailable']; } }));
    if (turn !== epoch) return;
    renderConnections([['Shopify', stores], ...results, ['Meta Ads', null]]);
    editGoal(); show('workspace-content', true); say('Workspace loaded.');
  }
  $('retry').onclick = () => guarded(session);
  $('logout').onclick = () => guarded(async () => { await request('/api/customer/v1/session', 'DELETE'); epoch++; invalidate(); show('application', false); show('logout', false); show('signed-out', true); say('Signed out.'); });
  $('workspace').onchange = () => guarded(loadWorkspace);
  $('goal').onchange = editGoal;
  $('store').onchange = updateBasis;
  $('goal-form').oninput = () => { invalidate(); show('preview', false); };
  $('provision').onsubmit = event => { event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget)); guarded(async () => {
    const encoded = JSON.stringify(body);
    if (encoded !== signupBody) { signupBody = encoded; signupKey = crypto.randomUUID(); }
    const workspace = await request('/api/customer/v1/workspaces', 'POST', body, {'Idempotency-Key': signupKey});
    signupKey = null; signupBody = null; await session(); $('workspace').value = workspace.id; await loadWorkspace();
  }); };
  $('goal-form').onsubmit = event => { event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget)); guarded(async () => {
    const definition = definitionFrom(values, stores.find(s => s.id === values.store_id && s.status === 'active'));
    const item = await request(root() + '/goals' + (selectedGoal ? '/' + selectedGoal.id : ''), selectedGoal ? 'PUT' : 'POST', {...(selectedGoal ? {expected_revision: selectedGoal.revision} : {}), definition});
    await loadWorkspace(); $('goal').value = item.id; editGoal(); say('Goal draft saved. Review its baseline before confirming.');
  }); };
  $('preview').onclick = () => guarded(async () => {
    invalidate();
    const preview = await request(root() + `/goals/${selectedGoal.id}/preview`, 'POST', {expected_revision: selectedGoal.revision});
    const snapshot = await request(root() + `/commerce/snapshots/${preview.snapshot_id}`);
    reviewed = {...preview, goal_id: selectedGoal.id, key: crypto.randomUUID()};
    $('review-data').replaceChildren();
    summary($('review-data'), goalSummary(selectedGoal.definition));
    $('review-data').append(textNode('h4', 'Historical Baseline'));
    summary($('review-data'), [['Readiness', snapshot.quality === 'complete' ? 'Ready To Review' : 'Not Ready'], ['Baseline Sales', amount(snapshot.quality === 'complete' ? snapshot.net_sales_micros : null, snapshot.currency)], ['Baseline Period', period(snapshot.window)], ['Orders', String(snapshot.orders ?? 'Not Available')]]);
    for (const warning of baselineWarnings(snapshot.reasons)) $('review-data').append(textNode('p', warning));
    if (snapshot.quality !== 'complete') { reviewed = null; $('review-data').append(textNode('p', 'Confirmation is unavailable until the baseline is complete.')); }
    show('confirm', snapshot.quality === 'complete'); show('review', true); say('Review the goal and baseline below.');
  });
  $('confirm').onclick = () => guarded(async () => {
    if (!reviewed || reviewed.goal_id !== selectedGoal?.id || reviewed.revision !== selectedGoal.revision) throw new Error('Review the current goal first.');
    const id = selectedGoal.id;
    await request(root() + `/goals/${id}/confirm`, 'POST', {expected_revision: reviewed.revision, preview_id: reviewed.preview_id, idempotency_key: reviewed.key});
    await loadWorkspace(); $('goal').value = id; editGoal(); say('Goal confirmed. Advertising spending remains unauthorized.');
  });
  for (const kind of ['checkout', 'management']) $(kind).onclick = () => guarded(async () => { const result = await request(root() + '/billing/' + kind, 'POST'); location.assign(billingDestination(result, kind)); });
  guarded(session);
}
