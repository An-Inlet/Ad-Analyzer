const $ = id => document.getElementById(id);
const base = '/api/customer/v1';
const amount = value => { const n = BigInt(value); const fraction = (n % 1000000n).toString().padStart(6, '0').replace(/0+$/, ''); return `${n / 1000000n}${fraction ? '.' + fraction : ''}`; };
const node = (tag, value) => { const n = document.createElement(tag); n.textContent = value; return n; };
let wid = '', drafts = [], draft = null, platform = '', saved = null, busy = false, configurations = [];
let mediaReady = false, generation = 0, urls = [], abort = null;
const path = suffix => `/workspaces/${wid}/execution/social${suffix}`;
function options(id, rows, label, key) {
  const first = node('option', 'Choose…'); first.value = ''; $(id).replaceChildren(first);
  for (const row of rows) { const o = node('option', label(row)); o.value = row[key]; o.disabled = row.review_available === false; $(id).append(o); }
}
function headers(method) {
  const h = {Accept: 'application/json'};
  if (method !== 'GET') {
    const csrf = document.cookie.split(';').map(x => x.trim()).find(x => x.startsWith('__Host-inlet_csrf='))?.split('=')[1];
    if (!/^[A-Za-z0-9_-]{43}$/.test(csrf || '')) throw Object.assign(new Error('Sign in again.'), {status: 401});
    h['X-CSRF-Token'] = csrf; h['Content-Type'] = 'application/json';
  }
  return h;
}
async function api(url, method = 'GET', body) {
  const r = await fetch(base + url, {method, headers: headers(method), credentials: 'same-origin', redirect: 'error', cache: 'no-store', body: body === undefined ? undefined : JSON.stringify(body)});
  if (!r.ok) throw Object.assign(new Error(({401:'Sign in again.',403:'Current owner access is required.',409:'The configuration changed or is not supported. Load and review it again.',422:'Choose the requested settings. Personal declaration names are not accepted.',503:'Verified social configuration discovery is not configured. This review remains unavailable.'})[r.status] || 'The review is unavailable.'), {status:r.status});
  return r.status === 204 ? null : r.json();
}
function clearMedia() {
  generation++; abort?.abort(); abort = null; mediaReady = false;
  const video = $('social-video'); video.pause(); video.removeAttribute('src'); video.load();
  for (const id of ['social-image','social-cover-image','social-video']) { $(id).removeAttribute('src'); $(id).hidden = true; }
  urls.forEach(url => URL.revokeObjectURL(url)); urls = [];
  $('social-media-status').textContent = ''; $('social-ack').checked = false;
}
function invalidate() { saved = null; $('social-review').hidden = true; $('social-summary').replaceChildren(); $('social-ack').checked = false; enable(); }
function enable() {
  for (const element of document.querySelectorAll('button,select,input')) element.disabled = busy;
  $('social-save').disabled = busy || !mediaReady || !configurations.find(o => o.id === $('social-option').value)?.review_available || (platform === 'meta_ads' && !$('social-category').value);
  $('social-confirm').disabled = busy || !saved || !mediaReady || !$('social-ack').checked || saved.blockers.length > 0 || saved.status === 'requires_new_review';
}
async function guarded(fn) {
  if (busy) return; busy = true; enable();
  try { await fn(); } catch (e) {
    $('social-message').textContent = e.message;
    invalidate(); clearMedia();
    if (e.status === 401 || e.status === 403) { $('social-select').hidden = true; $('social-settings').hidden = true; }
  } finally { busy = false; enable(); }
}
async function mediaBlob(binding, signal) {
  const r = await fetch(base + `/workspaces/${wid}/media/${binding.media_id}`, {credentials:'same-origin', redirect:'error', cache:'no-store', signal});
  if (!r.ok || !r.body || r.headers.get('content-type')?.split(';')[0] !== binding.mime) throw new Error('Private media is unavailable.');
  const chunks = [], reader = r.body.getReader(); let length = 0;
  try { while (true) { const {done, value} = await reader.read(); if (done) break; length += value.byteLength; if (length > 64 * 1024 * 1024) throw new Error('Media exceeds the supported size.'); chunks.push(value); } }
  catch (error) { await reader.cancel(); throw error; }
  return new Blob(chunks, {type: binding.mime});
}
async function showPair(primary, cover) {
  clearMedia(); const epoch = generation; const controller = new AbortController(); abort = controller;
  const timer = setTimeout(() => controller.abort(), 30000);
  $('social-media-status').textContent = 'Loading Exact Private Media…';
  try {
    for (const [binding, id] of [[primary, primary.mime === 'video/mp4' ? 'social-video' : 'social-image'], [cover, 'social-cover-image']]) {
      if (!binding) continue;
      const blob = await mediaBlob(binding, controller.signal); if (epoch !== generation) return;
      const url = URL.createObjectURL(blob); urls.push(url); const element = $(id); element.hidden = false;
      await new Promise((resolve, reject) => {
        const success = () => { cleanup(); resolve(); }, fail = () => { cleanup(); reject(new Error('The supplied media could not be decoded.')); };
        const event = binding.mime === 'video/mp4' ? 'loadeddata' : 'load';
        const cleanup = () => { element.removeEventListener(event, success); element.removeEventListener('error', fail); controller.signal.removeEventListener('abort', fail); };
        element.addEventListener(event, success, {once:true}); element.addEventListener('error', fail, {once:true}); controller.signal.addEventListener('abort', fail, {once:true}); element.src = url;
      });
    }
    if (epoch === generation) { mediaReady = true; $('social-media-status').textContent = 'Exact Supplied Media Loaded'; }
  } finally { clearTimeout(timer); enable(); }
}
function summary(review) {
  $('social-summary').replaceChildren();
  const add = (name, value) => $('social-summary').append(node('dt', name), node('dd', value));
  const c = review.configuration;
  add('Reviewed Requirements', review.requirements_text || 'Historical Wording Unavailable; New Review Required');
  add('Platform', review.platform === 'meta_ads' ? 'Meta Ads' : 'TikTok Ads');
  add('Environment', review.environment === 'contract_test' ? 'Contract Test · No Provider Changes' : 'Separate Execution Approval Required');
  add('Campaign', review.campaign.name); add('Campaign Period', `${review.campaign.starts_at} to ${review.campaign.ends_at}`); add('Landing Page', review.campaign.landing_page);
  add('Countries', review.countries.join(', ')); add('Languages', review.languages.join(', '));
  if (c) {
    add('Modeled Lifetime Budget', `${amount(c.reservation_micros)} ${c.currency}`);
    add('Account Time Zone', c.account_timezone); add('Activation', 'Separate Exact Approval');
    add('Budget Meaning', 'Lifetime Budget; Not An Independent Hard Spending Cap');
    if (review.platform === 'meta_ads') {
      add('Special Category Answer', {none_applicable:'None Apply',applicable:'A Category Applies · Unsupported',unsure:'Not Sure · Unsupported'}[review.answer.special_category_answer]);
      add('Age Range', `${c.age_min}–${c.age_max}`); add('Placement', 'Facebook Feed');
      add('Objective', 'Website Purchases'); add('Attribution', c.attribution.map(x => `${x.event_type === 'CLICK_THROUGH' ? 'Click' : 'View'} · ${x.window_days} Day(s)`).join('; '));
      add('Audience Expansion', 'Disabled'); add('Dynamic Creative', 'Disabled'); add('Landing Page Tracking Parameters', c.url_tags || 'None'); add('Budget Sharing', 'Disabled'); add('Bidding', 'Lowest Cost Without A Bid Cap');
    } else {
      add('Age Groups', c.age_groups.map(x => x.replace('AGE_','').replaceAll('_','–')).join(', '));
      add('Placement', 'TikTok'); add('Objective', 'Website Purchases');
      add('Click Attribution', c.click_attribution_window.replaceAll('_',' ')); add('View Attribution', c.view_attribution_window.replaceAll('_',' '));
      add('Engaged View Attribution', c.engaged_view_attribution_window.replaceAll('_',' '));
      add('Comments', c.comment_disabled ? 'Disabled' : 'Enabled'); add('Sharing', c.share_disabled ? 'Disabled' : 'Enabled'); add('Downloads', c.video_download_disabled ? 'Disabled' : 'Enabled');
      add('Smart Audience And Interests', 'Disabled'); add('Search Placement', 'Disabled'); add('Delivery Pacing', 'Smooth'); add('Bidding', 'No Bid'); add('Offsite Tracking URLs', 'None');
    }
  }
  $('social-state').textContent = review.blockers.length ? 'This Answer Requires An Unsupported Configuration. Confirmation Is Blocked.' : review.status === 'confirmed_historical' ? 'Confirmation Recorded. Current Provider Qualification And Separate Execution Approval Still Required.' : review.publication;
  $('social-ack').checked = false; $('social-review').hidden = false;
}
async function session() {
  await api('/session'); const workspaces = await api('/workspaces'); options('social-workspace', workspaces, x => x.name, 'id');
  $('social-select').hidden = false; $('social-logout').hidden = false; $('social-message').textContent = 'Choose A Workspace And An Approved Campaign.';
}
if (typeof document !== 'undefined') {
  $('social-workspace').onchange = () => guarded(async () => { invalidate(); clearMedia(); $('social-settings').hidden = true; wid = $('social-workspace').value; if (!wid) return; drafts = await api(`/workspaces/${wid}/campaign-drafts`); options('social-draft', drafts, x => x.name, 'draft_id'); });
  $('social-draft').onchange = () => { invalidate(); clearMedia(); $('social-settings').hidden = true; };
  $('social-load').onclick = () => guarded(async () => {
    invalidate(); clearMedia(); draft = drafts.find(x => x.draft_id === $('social-draft').value); if (!draft) throw new Error('Choose an approved campaign.');
    const catalog = await api(path('/options'), 'POST', {draft_id:draft.draft_id,draft_revision:draft.revision}); platform = catalog.platform;
    configurations = catalog.options; options('social-option', catalog.options, x => x.name, 'id'); $('social-requirements').textContent = 'Choose A Configuration To Read Its Reviewed Requirements.'; $('social-environment').textContent = catalog.environment === 'contract_test' ? 'Contract Test · No Provider Changes' : 'Configuration Review Only';
    $('social-meta').hidden = platform !== 'meta_ads'; $('social-tiktok').hidden = platform !== 'tiktok_ads'; $('social-category').value = '';
    const preview = await api(`/workspaces/${wid}/campaign-drafts/${draft.draft_id}/preview`); draft.primary = preview.artifact.definition.content.media;
    const library = await api(`/workspaces/${wid}/media`); draft.library = library; draft.primary = library.find(x => x.media_id === draft.primary.media_id); if (!draft.primary) throw new Error('Original private media is unavailable.');
    options('social-cover', library.filter(x => x.mime.startsWith('image/')), (x, i) => `Image · ${x.width} × ${x.height} · ${x.size} Bytes`, 'media_id');
    $('social-settings').hidden = false; $('social-message').textContent = catalog.blockers.includes('tiktok_native_catalog_parser_unverified') ? 'TikTok Account Discovery Is Not Yet Verified. Publication Remains Unavailable.' : 'Provider Qualification Remains Blocked Until Separately Verified.';
    if (platform === 'meta_ads') await showPair(draft.primary, null);
  });
  $('social-option').onchange = () => { invalidate(); $('social-requirements').textContent = configurations.find(o => o.id === $('social-option').value)?.requirements_text || 'Verified Requirements Are Unavailable.'; }; $('social-category').onchange = () => invalidate();
  $('social-cover').onchange = () => guarded(async () => { invalidate(); const cover = draft.library.find(x => x.media_id === $('social-cover').value); if (!cover) { clearMedia(); return; } await showPair(draft.primary, cover); });
  $('social-save').onclick = () => guarded(async () => {
    saved = await api(path('/reviews'), 'POST', {draft_id:draft.draft_id,draft_revision:draft.revision,option_id:$('social-option').value,answer:platform === 'meta_ads' ? {kind:'meta_no_dsa',special_category_answer:$('social-category').value} : {kind:'tiktok_cover',reviewed_pair:true},cover_media_id:platform === 'tiktok_ads' ? $('social-cover').value : null});
    summary(saved); await showPair(saved.primary, saved.cover);
  });
  $('social-ack').onchange = enable;
  $('social-confirm').onclick = () => guarded(async () => { saved = await api(path(`/reviews/${saved.id}/confirmation`), 'POST', {expected_digest:saved.digest,acknowledged:true}); summary(saved); $('social-message').textContent = 'Exact Configuration Confirmation Recorded. No Ads Were Published.'; });
  $('social-logout').onclick = () => guarded(async () => { invalidate(); clearMedia(); $('social-settings').hidden = true; $('social-select').hidden = true; $('social-logout').hidden = true; await api('/session','DELETE'); $('social-message').textContent = 'Signed Out.'; });
  addEventListener('pagehide', clearMedia); guarded(session);
}
