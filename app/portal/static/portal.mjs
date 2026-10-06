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
  if (!['checkout', 'management'].includes(kind) || typeof result.url !== 'string' || result.url.length > 2048) throw new Error('Billing returned an invalid destination.');
  const host = kind === 'checkout' ? 'checkout.stripe.com' : 'billing.stripe.com';
  if (url.protocol !== 'https:' || url.hostname !== host || url.port || url.username || url.password || (kind === 'checkout' ? !url.pathname.startsWith('/c/') : !url.pathname.startsWith('/p/session/'))) throw new Error('Billing returned an invalid destination.');
  return url.href;
}
export function shopifyDestination(result, shop) {
  const domain = shop.trim().toLowerCase();
  if (!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.myshopify\.com$/.test(domain)) throw new Error('Enter your store’s myshopify.com domain without a URL or path.');
  const url = new URL(result.authorization_url);
  if (url.protocol !== 'https:' || url.hostname !== domain || url.port || url.username || url.password || url.pathname !== '/admin/oauth/authorize' || url.hash) throw new Error('Shopify returned an invalid authorization destination.');
  return url.href;
}
export function googleDestination(result, configuration, origin) {
  const url = new URL(result.authorization_url);
  const expected = {client_id: configuration.client_id, redirect_uri: origin + '/api/customer/v1/google/callback', response_type: 'code', scope: 'https://www.googleapis.com/auth/adwords', access_type: 'offline', prompt: 'consent'};
  if (configuration.redirect_uri !== expected.redirect_uri || url.protocol !== 'https:' || url.hostname !== 'accounts.google.com' || url.port || url.username || url.password || url.pathname !== '/o/oauth2/v2/auth' || url.hash) throw new Error('Google returned an invalid authorization destination.');
  for (const [key, value] of Object.entries(expected)) if (!value || url.searchParams.getAll(key).length !== 1 || url.searchParams.get(key) !== value) throw new Error('Google authorization configuration changed. Reload before trying again.');
  if ([...url.searchParams.keys()].some(key => !Object.hasOwn(expected, key) && key !== 'state') || url.searchParams.getAll('state').length !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(url.searchParams.get('state') || '')) throw new Error('Google authorization request is invalid.');
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
    const error = new Error(({401: 'Your session has ended. Sign in again.', 403: 'Your role or session does not permit this action.', 404: 'This item is unavailable in your workspace.', 409: 'The saved state changed or is not ready. Reload and review before trying again.', 422: 'Check the entered values and measurement periods.', 429: 'Usage limit reached. Try again later.', 502: 'The provider is temporarily unavailable.', 503: 'This service is not configured or is temporarily unavailable.'})[response.status] || 'The request could not be completed.');
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
  let workspaces = [], stores = [], goals = [], selectedGoal = null, reviewed = null, epoch = 0, googleSetup = null, googleConnections = [];
  let signupKey = null, signupBody = null, busyCount = 0, controlStates = null;

  const pendingGoals = new Map();
  class StaleRequest extends Error {}
  async function api(...args) {
    const turn = epoch;
    try {
      const result = await request(...args);
      if (turn !== epoch) throw new StaleRequest();
      return result;
    } catch (error) {
      if (turn !== epoch) throw new StaleRequest();
      throw error;
    }
  }
  function clearWorkspace() {
    epoch++; stores = []; goals = []; selectedGoal = null; reviewed = null;
    for (const id of ['store', 'goal', 'goal-detail', 'review-data', 'connections', 'mandates', 'billing', 'billing-detail', 'basis']) $(id).replaceChildren();
    $('goal-form').reset(); $('shopify-connect').reset(); $('shopify-current').textContent = '';
    googleSetup = null; googleConnections = []; $('google-disconnect-consent').checked = false; $('google-disconnect-account').replaceChildren(); $('shopify-disconnect-consent').checked = false;
    for (const id of ['workspace-content', 'review', 'preview', 'checkout', 'management', 'billing-refresh', 'shopify-setup', 'shopify-disconnect-open', 'shopify-disconnect-review', 'google-setup', 'google-authorize', 'google-disconnect', 'google-disconnect-review']) show(id, false);

  }
  function clearSession() {
    clearWorkspace(); workspaces = []; pendingGoals.clear(); signupKey = null; signupBody = null;
    $('workspace').replaceChildren(); $('provision').reset();
    show('application', false); show('signed-out', true); show('logout', false);
  }
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
        for (const value of [name + (connection?.external_account_id ? ` · ${connection.external_account_id}` : rows.length > 1 ? ` ${index + 1}` : ''), state, imported, attention]) row.append(textNode('td', value));
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
    if (busyCount === 0) controlStates = new Map(controls.map(c => [c, c.disabled]));
    busyCount++;
    controls.forEach(c => { c.disabled = true; });
    try { await task(); } catch (error) {
      if (error instanceof StaleRequest) return;
      if (error.status === 401) clearSession();
      say(error.message, true);
    } finally {
      busyCount--;
      if (busyCount === 0) { for (const [control, disabled] of controlStates) control.disabled = disabled; controlStates = null; }
    }
  }
  async function session() {
    clearSession();
    try {
      await api('/api/customer/v1/session');
      workspaces = await api('/api/customer/v1/workspaces');
      $('workspace').replaceChildren(option('', 'Select A Workspace'), ...workspaces.map(w => option(w.id, `${w.name} · ${w.role}`)));
      show('application', true); show('signed-out', false); show('logout', true); say('Choose or create a workspace.');
      const requested = new URLSearchParams(location.search).get('workspace');
      if (location.search) history.replaceState(null, '', location.pathname);
      if (requested && workspaces.some(w => String(w.id) === requested)) { $('workspace').value = requested; await loadWorkspace(); }

    } catch (error) { if (error instanceof StaleRequest) return; clearSession(); say(error.message, true); }
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
    clearWorkspace(); const turn = epoch;
    if (!$('workspace').value) return;
    const path = root();
    const result = await Promise.all([api(path + '/commerce/stores'), api(path + '/goals'), api(path + '/mandates'), api(path + '/billing')]);
    if (turn !== epoch) throw new StaleRequest();
    [stores, goals] = result;
    $('store').replaceChildren(...stores.filter(s => s.status === 'active').map((s, i) => option(s.id, `Shopify Store ${i + 1} · ${s.currency} · ${s.time_zone}`)));
    $('goal').replaceChildren(option('', 'New Goal'), ...goals.map((g, i) => option(g.id, `Goal ${i + 1} · ${period(g.definition?.target_window)} · ${g.confirmation_recorded ? 'Confirmed' : 'Draft'}`)));
    renderMandates(result[2]);
    renderBilling(result[3]);
    const providers = [['Google Ads', '/google/connections'], ['TikTok Ads', '/sources/tiktok_ads'], ['Klaviyo', '/sources/klaviyo'], ['HubSpot', '/sources/hubspot'], ['Omnisend', '/sources/omnisend']];
    const results = await Promise.all(providers.map(async ([name, endpoint]) => { try { return [name, await api(path + endpoint)]; } catch (error) { if (error instanceof StaleRequest || error.status === 401) throw error; return [name, 'Status unavailable']; } }));
    if (turn !== epoch) throw new StaleRequest();
    renderConnections([['Shopify', stores], ...results, ['Meta Ads', null]]);
    const setup = await api(path + '/shopify/setup');
    if (turn !== epoch) throw new StaleRequest();
    show('shopify-setup', true); show('shopify-connect', Boolean(setup.enabled && setup.can_manage));
    $('shopify-setup-status').textContent = !setup.enabled ? 'Shopify connection setup is not configured.' : setup.can_manage ? 'An owner or admin can authorize this workspace’s store.' : 'Ask a workspace owner or admin to connect Shopify.';
    const connected = await api(path + '/shopify');
    if (turn !== epoch) throw new StaleRequest();
    if (connected.length) { $('shopify-domain').value = connected[0].shop_domain; $('shopify-current').textContent = `${connected[0].shop_domain} · ${label(connected[0].status)}`; }
    show('shopify-disconnect-open', Boolean(connected.length && setup.can_manage));
    googleSetup = await api(path + '/google/setup');
    if (turn !== epoch) throw new StaleRequest();
    show('google-setup', true); show('google-authorize', Boolean(googleSetup.enabled && googleSetup.can_manage));
    googleConnections = (results.find(([name]) => name === 'Google Ads')?.[1] || []);
    if (!Array.isArray(googleConnections)) googleConnections = [];
    googleConnections = googleConnections.filter(row => row.status !== 'disconnected');
    $('google-disconnect-account').replaceChildren(...googleConnections.map(row => option(row.id, `${row.external_account_id} · ${label(row.status)}`)));
    show('google-disconnect', Boolean(googleSetup.can_manage && googleConnections.length));
    $('google-setup-status').textContent = !googleSetup.enabled ? 'Google Ads connection setup is not configured.' : googleSetup.can_manage ? 'An owner or admin can connect an advertising account.' : 'Ask a workspace owner or admin to connect Google Ads.';

    editGoal(); show('workspace-content', true); say('Workspace loaded.');
  }
  $('shopify-disconnect-open').onclick = () => { $('shopify-disconnect-consent').checked = false; show('shopify-disconnect-review', true); };
  $('shopify-disconnect-cancel').onclick = () => { $('shopify-disconnect-consent').checked = false; show('shopify-disconnect-review', false); };
  $('shopify-disconnect-confirm').onclick = () => guarded(async () => {
    if (!$('shopify-disconnect-consent').checked) throw new Error('Confirm the data effects before disconnecting Shopify.');
    await api(root() + '/shopify', 'DELETE'); await loadWorkspace();
    say('Shopify disconnected and imported data removed. Saved goal history remains; reconnect and import before reconfirming.');
  });
  const cancelGoogleDisconnect = () => { $('google-disconnect-consent').checked = false; show('google-disconnect-review', false); };
  $('google-disconnect-account').onchange = cancelGoogleDisconnect;
  $('google-disconnect-cancel').onclick = cancelGoogleDisconnect;
  $('google-disconnect-open').onclick = () => { $('google-disconnect-consent').checked = false; show('google-disconnect-review', true); };
  $('google-disconnect-confirm').onclick = () => guarded(async () => {
    const selected = googleConnections.find(row => row.id === $('google-disconnect-account').value);
    if (!googleSetup?.can_manage || !selected || !$('google-disconnect-consent').checked) throw new Error('Select an account and confirm the data effects before disconnecting Google Ads.');
    await api(root() + '/google/connections/' + encodeURIComponent(selected.id), 'DELETE');
    await loadWorkspace();
    say('Google Ads disconnected. Historical data remains; imports have stopped. Running campaigns and spending are unchanged.');
  });
  $('google-authorize').onclick = () => guarded(async () => {
    if (!googleSetup?.enabled || !googleSetup.can_manage) throw new Error('Google Ads setup is unavailable for this session.');
    const result = await api(root() + '/google/authorize', 'POST');
    location.assign(googleDestination(result, googleSetup, location.origin));
  });
  $('shopify-connect').onsubmit = event => { event.preventDefault(); guarded(async () => {
    const shop = $('shopify-domain').value.trim().toLowerCase();
    shopifyDestination({authorization_url: `https://${shop}/admin/oauth/authorize`}, shop);
    const result = await api(root() + '/shopify/authorize', 'POST', {shop});
    location.assign(shopifyDestination(result, shop));
  }); };
  window.addEventListener('pageshow', event => { if (event.persisted) guarded(session); });
  function renderBilling(billing) {
    $('billing').textContent = `${label(billing.status)} · ${billing.mode === 'stripe_test' ? 'Test Billing Only' : 'Purchasing Unavailable'}`;
    $('billing-detail').replaceChildren();
    for (const message of [
      'Returning from Stripe does not confirm payment. Access changes only after verified server reconciliation.',
      billing.checkout_pending ? 'Checkout is pending. If you canceled or lost the response, resume the same checkout safely; do not assume a payment succeeded.' : null,
      billing.verification_current ? 'Subscription status was recently verified by the server.' : 'Subscription status has not been recently verified. Check again after processing.',
      billing.cancel_at_period_end ? 'Cancellation is scheduled at the end of the current period.' : null,
      billing.needs_attention ? 'Billing needs attention. Check its status again; contact support if reconciliation remains unavailable.' : null,
    ].filter(Boolean)) $('billing-detail').append(textNode('p', message));
    if (billing.period_end) $('billing-detail').append(textNode('p', `Current Period Ends: ${new Date(billing.period_end).toLocaleString('en-US', {timeZone:'UTC'})} UTC`));
    const owner = workspaces.find(w => String(w.id) === $('workspace').value)?.role === 'owner';
    show('checkout', Boolean(owner && billing.mode === 'stripe_test' && billing.can_checkout));
    show('management', Boolean(owner && billing.mode === 'stripe_test' && billing.can_manage));
    $('checkout').textContent = billing.checkout_pending ? 'Resume Test Checkout' : 'Open Test Checkout';
    show('billing-refresh', true);
  }
  async function refreshBilling() {
    try { renderBilling(await api(root() + '/billing')); }
    catch (error) {
      if (error instanceof StaleRequest) throw error;
      $('billing').textContent = ''; $('billing-detail').replaceChildren();
      show('checkout', false); show('management', false);
      throw error;
    }
  }
  $('billing-refresh').onclick = () => guarded(refreshBilling);
  $('retry').onclick = () => guarded(session);
  // Auth is lazy and disabled by server configuration; no SDK/provider network by default.
  import('./auth.mjs').then(async ({prepareSignIn}) => {
    const signIn = await prepareSignIn();
    if (!signIn) return;
    $('signin-status').textContent = 'Use Google to create an Inlet account or sign in. Live setup has not been verified.';
    show('signin', true);
    $('signin').onclick = () => guarded(async () => {
      clearSession();
      await signIn();
      await session();
    });
  }).catch(() => { $('signin-status').textContent = 'Customer sign-in is unavailable. You can check an existing session.'; });
  $('logout').onclick = () => guarded(async () => { clearSession(); await api('/api/customer/v1/session', 'DELETE'); say('Signed out.'); });
  $('workspace').onchange = () => guarded(loadWorkspace);
  $('goal').onchange = editGoal;
  $('store').onchange = updateBasis;
  $('goal-form').oninput = () => { invalidate(); show('preview', false); };
  $('provision').onsubmit = event => { event.preventDefault(); const body = Object.fromEntries(new FormData(event.currentTarget)); guarded(async () => {
    const encoded = JSON.stringify(body);
    if (encoded !== signupBody) { signupBody = encoded; signupKey = crypto.randomUUID(); }
    const workspace = await api('/api/customer/v1/workspaces', 'POST', body, {'Idempotency-Key': signupKey});
    signupKey = null; signupBody = null; await session(); $('workspace').value = workspace.id; await loadWorkspace();
  }); };
  $('goal-form').onsubmit = event => { event.preventDefault(); const values = Object.fromEntries(new FormData(event.currentTarget)); guarded(async () => {
    const definition = definitionFrom(values, stores.find(s => s.id === values.store_id && s.status === 'active'));
    const path = root();
    let headers = {};
    if (!selectedGoal) {
      const encoded = JSON.stringify(definition);
      const pending = pendingGoals.get(path);
      if (pending && pending.body !== encoded) throw new Error('The previous save has an unknown outcome. Restore its values and retry before creating a different goal.');
      if (!pending) pendingGoals.set(path, {body: encoded, key: crypto.randomUUID()});
      headers = {'Idempotency-Key': pendingGoals.get(path).key};
    }
    const creationKey = headers['Idempotency-Key'];
    const settleCreation = () => {
      if (creationKey && pendingGoals.get(path)?.key === creationKey) pendingGoals.delete(path);
    };
    let item;
    try {
      item = await api(path + '/goals' + (selectedGoal ? '/' + selectedGoal.id : ''), selectedGoal ? 'PUT' : 'POST', {...(selectedGoal ? {expected_revision: selectedGoal.revision} : {}), definition}, headers);
    } catch (error) {
      // This endpoint validates input before committing. Transport/5xx uncertainty
      // must retain the key, and edits must never settle another creation attempt.
      if (error.status === 422) settleCreation();
      throw error;
    }
    settleCreation();
    await loadWorkspace(); $('goal').value = item.id; editGoal(); say('Goal draft saved. Review its baseline before confirming.');
  }); };
  $('preview').onclick = () => guarded(async () => {
    invalidate();
    const preview = await api(root() + `/goals/${selectedGoal.id}/preview`, 'POST', {expected_revision: selectedGoal.revision});
    const snapshot = await api(root() + `/commerce/snapshots/${preview.snapshot_id}`);
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
    await api(root() + `/goals/${id}/confirm`, 'POST', {expected_revision: reviewed.revision, preview_id: reviewed.preview_id, idempotency_key: reviewed.key});
    await loadWorkspace(); $('goal').value = id; editGoal(); say('Goal confirmed. Advertising spending remains unauthorized.');
  });
  for (const kind of ['checkout', 'management']) $(kind).onclick = () => guarded(async () => {
    const path = root(), cookies = document.cookie;
    say(kind === 'checkout' ? 'Opening test checkout. If interrupted, check billing status and resume safely.' : 'Opening test subscription management.');
    try {
      const result = await api(path + '/billing/' + kind, 'POST');
      if (cookies !== document.cookie) { clearSession(); throw new Error('Your session changed. Sign in again before opening billing.'); }
      location.assign(billingDestination(result, kind));
    } catch (error) {
      if (error instanceof StaleRequest) throw error;
      if ([401, 403, 404].includes(error.status)) {
        $('billing').textContent = ''; $('billing-detail').replaceChildren(); show('checkout', false); show('management', false);
      } else {
        $('billing-detail').replaceChildren(textNode('p', 'The billing request did not finish. Check billing status, then resume the existing checkout if offered. Returning or retrying does not confirm payment.'));
      }
      throw error;
    }
  });
  guarded(session);
}
