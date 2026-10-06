const base = '/api/customer/v1';
const $ = id => document.getElementById(id);
let workspaces = [], selected = null, epoch = 0, busy = false, mediaReady = false;
const writer = () => ['owner', 'admin'].includes(workspaces.find(w => String(w.id) === $('review-workspace').value)?.role);
const root = () => `${base}/workspaces/${encodeURIComponent($('review-workspace').value)}`;
const item = () => `${root()}/campaign-drafts/${encodeURIComponent($('review-draft').value)}`;
const text = (tag, value) => { const node = document.createElement(tag); node.textContent = String(value); return node; };
const say = (message, error = false) => { $('review-status').textContent = message; $('review-status').className = error ? 'error' : ''; };
const labels = {google_ads: 'Google Ads', meta_ads: 'Meta Ads', tiktok_ads: 'TikTok Ads', website_sales: 'Website Sales', website_conversion: 'Website Conversion', capability_manifest_unqualified: 'This campaign type is not qualified for publication.', tracking_conversion_binding_required: 'Tracking and the account’s conversion setup need review.', bidding_configuration_required: 'Bidding settings need review.', publish_plan_unavailable: 'A complete publication plan is not available.', provider_publication_disabled: 'Provider publication is disabled.', video_validation_unavailable: 'Video validation is not available.'};
export function exactAmount(value, currency) {
  return `${currency} ${(value / 1000000).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 6})}`;
}
export function editedDefinition(original, values) {
  const result = structuredClone(original);
  if (!/^\d+(\.\d{1,6})?$/.test(values.budget)) throw new Error('Enter an amount with up to six decimal places.');
  const [whole, part = ''] = values.budget.split('.');
  const micros = Number(whole) * 1e6 + Number(part.padEnd(6, '0'));
  if (!Number.isSafeInteger(micros) || micros <= 0 || micros > 1e15) throw new Error('The budget is outside the allowed range.');
  result.budget_micros = micros;
  result.content.name = values.name; result.content.landing_page = values.landing_page;
  if (result.content.kind === 'google_search_v1') {
    for (const key of ['headlines', 'descriptions', 'exact_keywords']) result.content[key] = values[key].split('\n');
  } else {
    result.content.text = values.text;
    if (result.content.kind === 'meta_website_sales_image_v1') result.content.headline = values.headline;
  }
  return result;
}
async function api(path, method = 'GET', body) {
  const headers = {Accept: 'application/json'};
  if (method !== 'GET') {
    const csrf = document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith('__Host-inlet_csrf='))?.split('=')[1];
    if (!csrf || !/^[A-Za-z0-9_-]{43}$/.test(csrf)) throw new Error('Your session needs to be refreshed. Return to your workspace to sign in.');
    headers['X-CSRF-Token'] = csrf; headers['Content-Type'] = 'application/json';
  }
  const response = await fetch(path, {method, headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin', redirect: 'error', cache: 'no-store'});
  if (!response.ok) {
    const error = new Error(({401: 'Sign In Required. Return to your workspace to sign in.', 403: 'Your role or session does not permit this action.', 404: 'This draft or workspace is unavailable.', 409: 'This review changed or its account, mandate or media is no longer ready. Reload and review the current revision.', 422: 'Check the supplied copy, HTTPS landing page and budget. Google headlines allow 30 characters, descriptions 90 and keywords 80 characters / 10 words; double-width ad characters count twice.', 503: 'Private media or another required service is unavailable. Approval is blocked.'})[response.status] || 'The request could not be completed. Reload before trying again.');
    error.status = response.status; throw error;
  }
  return response.json();
}
function enable() {
  for (const id of ["review-workspace", "review-draft", "review-reload"]) $(id).disabled = busy;
  $('approve-campaign').disabled = busy || !selected || !writer() || !mediaReady || !selected.artifact.offline_reviewable || selected.approved_for_offline_plan || !$('review-consent').checked;
  $('save-campaign').disabled = busy || !selected || !writer();
}
function clear() {
  selected = null; mediaReady = false; $('review-consent').checked = false;
  for (const id of ["campaign-title", "approval-status", "campaign-summary", "campaign-copy", "media-status", "publication-blockers", "review-reference"]) $(id).replaceChildren();
  $("campaign-edit").reset();
  $('campaign-media').onload = null; $('campaign-media').onerror = null;
  $('campaign-media').removeAttribute('src'); $('campaign-media').hidden = true;
  $('campaign-preview').hidden = true; $('campaign-editor').hidden = true; enable();
}
async function guarded(action) {
  if (busy) return;
  busy = true; enable();
  try { await action(); } catch (error) {
    // Never retain an approvable stale preview after any failed action/read.
    clear();
    if (error.status === 401 || error.status === 403) { ++epoch; workspaces = []; choices($("review-workspace"), [], "Sign In Again", "id", row => row.name); choices($("review-draft"), [], "Select A Draft", "draft_id", row => row.name); }
    say(error.message, true);
  } finally { busy = false; enable(); }
}
function choices(element, rows, prompt, key, name) {
  element.replaceChildren(); const first = text('option', prompt); first.value = ''; element.append(first);
  for (const row of rows) { const option = text('option', name(row)); option.value = String(row[key]); element.append(option); }
}
function render(row, currentEpoch, scopeRoot) {
  selected = row; const a = row.artifact, d = a.definition, c = d.content;
  $('campaign-title').textContent = c.name;
  $('approval-status').textContent = `Revision ${row.revision} · ${row.approved_for_offline_plan ? 'Approved For Offline Planning' : 'Needs Your Review'}`;
  const summary = document.createElement('dl');
  const fields = [['Platform', labels[d.account.platform]], ['Objective', labels[c.objective]], ['Advertising Account', d.account.account_id], ['Connection', d.account.connection_id], ['Mandate', `${d.mandate_id} · Revision ${d.mandate_revision}`], ['Landing Page', c.landing_page], ['Total Modeled Exposure', exactAmount(d.budget_micros, d.currency)], ['Starts At', d.starts_at], ['Ends At', d.ends_at], ['Countries', c.audience.countries.join(', ')], ['Languages', c.audience.languages.join(', ')]];
  if (c.call_to_action) fields.push(['Call To Action', 'Shop Now']);
  for (const [name, value] of fields) summary.append(text('dt', name), text('dd', value));
  $('campaign-summary').replaceChildren(summary); $('campaign-copy').replaceChildren();
  for (const [name, value] of Object.entries(c.kind === 'google_search_v1' ? {Headlines: c.headlines, Descriptions: c.descriptions, 'Exact Keywords': c.exact_keywords} : {Headline: c.headline, Text: c.text})) {
    if (value === undefined) continue;
    $('campaign-copy').append(text('h4', name));
    for (const line of Array.isArray(value) ? value : [value]) $('campaign-copy').append(text('p', line));
  }
  $('publication-blockers').replaceChildren(...[...(a.publication_blockers || []), ...(a.blockers || [])].map(reason => text('li', labels[reason] || 'Additional validation is required before publication.')));
  $('review-reference').textContent = `Revision ${row.revision} · ${row.review_digest}`;
  mediaReady = !c.media;
  if (!c.media) $('media-status').textContent = 'Text Campaign · No Supplied Media Required';
  else if (c.kind === 'tiktok_website_conversion_video_v1') {
    $('media-status').textContent = 'Video Validation Unavailable · Offline Approval Blocked';
  } else {
    $('media-status').textContent = 'Validated JPEG/PNG · Loading The Exact Supplied Image';
    const image = $('campaign-media');
    image.onload = () => { if (epoch !== currentEpoch || selected !== row) return; mediaReady = true; $('media-status').textContent = 'Validated Static Image · Exact Supplied Media Loaded'; enable(); };
    image.onerror = () => { if (epoch !== currentEpoch || selected !== row) return; mediaReady = false; $('media-status').textContent = 'Media Unavailable · Approval Blocked. Reload To Try Again.'; enable(); };
    image.hidden = false; image.src = `${scopeRoot}/media/${encodeURIComponent(c.media.media_id)}`;
  }
  const form = $('campaign-edit');
  for (const key of ['name', 'landing_page', 'headline', 'text']) form.elements.namedItem(key).value = c[key] || '';
  form.elements.namedItem('budget').value = (d.budget_micros / 1e6).toFixed(6);
  for (const key of ['headlines', 'descriptions', 'exact_keywords']) form.elements.namedItem(key).value = (c[key] || []).join('\n');
  $('google-copy-fields').hidden = c.kind !== 'google_search_v1'; $('social-copy-fields').hidden = c.kind === 'google_search_v1'; $('meta-headline-label').hidden = c.kind !== 'meta_website_sales_image_v1';
  $('campaign-preview').hidden = false; $('campaign-editor').hidden = !writer();
  $('review-consent').disabled = !writer() || row.approved_for_offline_plan;
  say(writer() ? 'Review the current revision before approving.' : 'Read-Only Review · An owner or admin must approve.'); enable();
}
async function preview() {
  clear(); const token = ++epoch;
  if (!$('review-workspace').value || !$('review-draft').value) return;
  const scopeRoot = root(); const row = await api(item() + '/preview');
  if (token === epoch) render(row, token, scopeRoot);
}
async function loadDrafts() {
  clear(); const token = ++epoch; choices($('review-draft'), [], 'Select A Draft', 'draft_id', row => row.name);
  if (!$('review-workspace').value) return;
  const rows = await api(root() + '/campaign-drafts');
  if (token !== epoch) return;
  choices($('review-draft'), rows, rows.length ? 'Select A Draft' : 'No Saved Drafts', 'draft_id', row => `${row.name} · Revision ${row.revision}`);
  say(rows.length ? 'Choose a draft to review.' : 'There are no saved campaign drafts in this workspace.');
}
if (typeof document !== 'undefined') {
  $('review-workspace').onchange = () => { ++epoch; clear(); guarded(loadDrafts); };
  $('review-draft').onchange = () => { ++epoch; clear(); guarded(preview); };
  $('review-reload').onclick = () => guarded(preview);
  $('review-consent').onchange = enable;
  $('approve-campaign').onclick = () => guarded(async () => {
    if (!selected || !writer() || !mediaReady || !selected.artifact.offline_reviewable || !$('review-consent').checked) throw new Error('Review the current plan first.');
    const snapshot = selected, token = epoch, path = item();
    clear();
    await api(path + '/approve', 'POST', {expected_revision: snapshot.revision, review_digest: snapshot.review_digest});
    if (token !== epoch) return;
    await preview(); say('This revision is approved for offline planning. Publication remains blocked.');
  });
  $('campaign-edit').onsubmit = event => { event.preventDefault(); guarded(async () => {
    if (!selected || !writer()) throw new Error('Load a current revision before editing.');
    const snapshot = selected, token = epoch, path = item();
    const definition = editedDefinition(snapshot.artifact.definition, Object.fromEntries(new FormData(event.target)));
    clear(); await api(path, 'PUT', {expected_revision: snapshot.revision, definition});
    if (token !== epoch) return;
    await preview(); say('New revision saved. Review it again before approving.');
  }); };
  guarded(async () => {
    await api(base + '/session'); workspaces = await api(base + '/workspaces');
    choices($('review-workspace'), workspaces, 'Select A Workspace', 'id', row => row.name);
    say('Choose a workspace and a saved draft.');
  });
}
