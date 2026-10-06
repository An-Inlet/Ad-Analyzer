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
export function metaDestination(result, configuration, origin) {
  const url = new URL(result.authorization_url);
  const expected = {client_id:configuration.client_id, redirect_uri:origin+'/api/customer/v1/meta/callback', scope:'ads_read', response_type:'code', auth_type:'rerequest'};
  if (url.origin !== 'https://www.facebook.com' || url.pathname !== '/v26.0/dialog/oauth' || url.username || url.password || url.hash || configuration.redirect_uri !== expected.redirect_uri || configuration.authorization_endpoint !== url.origin+url.pathname) throw new Error('Meta authorization destination is invalid.');
  for (const [key, value] of Object.entries(expected)) if (!value || url.searchParams.getAll(key).length !== 1 || url.searchParams.get(key) !== value) throw new Error('Meta configuration changed. Reload and retry.');
  if ([...url.searchParams.keys()].some(key => !Object.hasOwn(expected,key) && key !== 'state') || url.searchParams.getAll('state').length !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(url.searchParams.get('state') || '')) throw new Error('Meta authorization request is invalid.');
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
    googleSetup = null; googleConnections = []; metaSetup = null; $('meta-disconnect-consent').checked = false; $('google-disconnect-consent').checked = false; $('google-disconnect-account').replaceChildren(); $('shopify-disconnect-consent').checked = false;
    for (const id of ['workspace-content', 'review', 'preview', 'checkout', 'management', 'billing-refresh', 'shopify-setup', 'shopify-disconnect-open', 'shopify-disconnect-review', 'google-setup', 'google-authorize', 'google-disconnect', 'google-disconnect-review', 'meta-setup', 'meta-authorize', 'meta-disconnect', 'meta-disconnect-review']) show(id, false);

