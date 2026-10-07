const base = '/api/customer/v1';
const $ = id => document.getElementById(id);
const text = (tag, value) => { const node = document.createElement(tag); node.textContent = value; return node; };
let busy = false, signedIn = false, workspaces = [], preview = null, previewName = '', previewKey = null, currentReceipt = null;
const blockers = {publication_unresolved:'Advertising action outcomes still need verification.', billing_unresolved:'Billing and subscription obligations remain unresolved.', provider_revocation_unverified:'External provider permissions have not been verified revoked.', worker_not_quiescent:'In-flight work has not been verified stopped.', retention_policy_unset:'A retention and deletion policy still needs a decision.', media_generation_unavailable:'Private media cleanup evidence is unavailable.', legacy_scope_unclassified:'Some historical data ownership still needs review.', export_incomplete:'A complete export is not available.'};
export function receiptPath(pathname) {
  const match = /^\/app\/workspace-closure\/([1-9][0-9]*)\/([a-f0-9]{32})\/?$/.exec(pathname);
  if (!match || !Number.isSafeInteger(Number(match[1]))) return null;
  return {workspace_id:Number(match[1]),request_id:match[2]};
}
const link = row => `/app/workspace-closure/${row.scope.workspace_id}/${row.request_id}`;
function enable() {
  $('closure-workspace').disabled = busy;
  $('closure-preview').disabled = busy || !signedIn || !$('closure-workspace').value;
  $('closure-confirm').disabled = busy || !preview || $('closure-name').value !== previewName || !$('closure-ack').checked;
  $('closure-reconcile').disabled = busy || !signedIn || !currentReceipt;
  $('closure-logout').disabled = busy; $('closure-retry').disabled = busy;
}
function clear() {
  currentReceipt = null; $('closure-reconcile').hidden = true;
  preview = null; previewName = ''; $('closure-confirm-form').reset();
  for (const id of ['closure-review','closure-receipt']) $(id).hidden = true;
  for (const id of ['closure-target','closure-inventory','closure-preview-blockers','closure-digest','closure-receipt-target','closure-state','closure-effects','closure-data','closure-external','closure-blockers','closure-local-work']) $(id).replaceChildren();
  for (const id of ['closure-status-link','closure-preview-receipt']) $(id).removeAttribute('href');
  enable();
}
function signedOut() {
  signedIn = false; workspaces = []; previewKey = null; clear(); $('closure-selection').hidden = true;
  $('closure-workspace').replaceChildren(); $('closure-logout').hidden = true;
}
async function api(path, method = 'GET', body, key) {
  const headers = {Accept:'application/json'};
  if (method !== 'GET') {
    const csrf = document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('__Host-inlet_csrf='))?.split('=')[1];
    if (!csrf || !/^[A-Za-z0-9_-]{43}$/.test(csrf)) throw Object.assign(new Error('Sign in again before continuing.'),{status:401});
    headers['X-CSRF-Token'] = csrf; headers['Content-Type'] = 'application/json';
    if (key) headers['Idempotency-Key'] = key;
  }
  const response = await fetch(path,{method,headers,body:body === undefined ? undefined : JSON.stringify(body),credentials:'same-origin',redirect:'error',cache:'no-store'});
  if (!response.ok) throw Object.assign(new Error(({401:'Sign in to view this request or continue.',403:'Current workspace owner access is required.',404:'This workspace or closure request is unavailable to your account.',409:'The workspace inventory or request changed. Return to closure settings for a fresh preview.',422:'The exact workspace and reviewed inventory confirmation are required.',503:'The service is unavailable. Your closure has not been verified; check its status again.'})[response.status] || 'The request could not be verified. Check status before trying again.'),{status:response.status});
  return response.status === 204 ? null : response.json();
}
function displayBlockers(id, rows) { $(id).replaceChildren(...rows.map(row=>text('li',blockers[row.code] || 'An additional requirement is unresolved.'))); }
export function localReceiptConfirmed(row) {
  return row.schema_version === 'inlet.lifecycle.request.v1' && row.state === 'blocked' && Number.isSafeInteger(row.revision) && row.revision >= 2
    && row.closed === false && row.data_erased === false && row.provider_actions_verified === false;
}
function validateReceipt(row, target) {
  if (row.schema_version !== 'inlet.lifecycle.request.v1' || row.scope.workspace_id !== target.workspace_id || row.request_id !== target.request_id || row.closed !== false || row.data_erased !== false)
    throw new Error('Unexpected closure receipt. Check the current status with support.');
}
function renderReceipt(row) {
  clear(); $('closure-receipt').hidden = false;
  $('closure-receipt-target').textContent = `Workspace ${row.scope.workspace_id} · Request ${row.request_id}`;
  const localConfirmed = localReceiptConfirmed(row);
  currentReceipt = localConfirmed ? row : null; $('closure-reconcile').hidden = !localConfirmed;
  const observation = row.local_work;
  if (observation?.schema_version === 'inlet.lifecycle.local_quiescence.v1' && observation.observation_kind === 'current_only' && observation.physical_workers_stopped === null) {
    $('closure-local-work').textContent = `${observation.local_records_drained === true ? 'No Unknown Or Nonterminal Local Work Records Observed.' : 'Local Work Records Still Need Verification.'} This is a current database observation, not confirmation that worker processes stopped. Full closure remains blocked. ${observation.durable_receipt ? 'A verification digest is retained; the historical observation payload is not retained.' : 'Use Check Local Work to record a verification digest.'}`;
  }
  $('closure-state').textContent = localConfirmed ? 'Local Closure Confirmed · Full Closure Blocked' : row.state === 'requested' ? 'Preview Created · Closure Not Confirmed' : 'Closure Not Verified Complete';
  $('closure-effects').textContent = localConfirmed ? 'Inlet has removed local connection credentials and disabled new workspace work. In-flight work still requires verification.' : 'Local credential removal and work stoppage are not confirmed by this receipt.';
  $('closure-data').textContent = 'Historical data is retained. Complete closure and data erasure are not verified.';
  $('closure-external').textContent = 'External ads and provider permissions have not been changed or verified revoked. Billing and subscriptions are not canceled.';
  displayBlockers('closure-blockers',row.blockers || []); $('closure-status-link').href = link(row);
  $('closure-message').textContent = 'Current authenticated request status loaded.';
}
async function status(target) {
  clear(); $('closure-selection').hidden = true;
  const row = await api(`${base}/workspaces/${target.workspace_id}/closures/${target.request_id}`);
  validateReceipt(row,target);
  renderReceipt(row);
}
async function session() {
  signedOut(); await api(base+'/session'); signedIn = true; $('closure-logout').hidden = false;
  const target = receiptPath(location.pathname);
  if (target) { await status(target); return; }
  if (location.pathname.replace(/\/$/,'') !== '/app/workspace-closure') throw new Error('Invalid closure receipt link. Return to Settings.');
  workspaces = (await api(base+'/workspaces')).filter(w=>w.role === 'owner');
  const prompt = text('option','Select A Workspace'); prompt.value = ''; $('closure-workspace').replaceChildren(prompt);
  for (const workspace of workspaces) { const option = text('option',`${workspace.name} · Workspace ${workspace.id}`); option.value = String(workspace.id); $('closure-workspace').append(option); }
  $('closure-selection').hidden = false;
  $('closure-message').textContent = workspaces.length ? 'Choose the exact workspace to review. Nothing changes until confirmation.' : 'No active workspace with owner access is available. Use a saved request link to check a closing workspace.';
}
async function guarded(action) {
  if (busy) return; busy = true; enable();
  try { await action(); } catch(error) {
    clear(); if ([401,403,404].includes(error.status)) signedOut();
    $('closure-message').textContent = error.message || 'Status unavailable. Try checking again.';
  } finally { busy = false; enable(); }
}
if (typeof document !== 'undefined') {
  $('closure-workspace').onchange = () => { clear(); previewKey = null; };
  $('closure-name').oninput = enable; $('closure-ack').onchange = enable;
  $('closure-retry').onclick = () => guarded(session);
  $('closure-reconcile').onclick = () => guarded(async()=>{
    const frozen = currentReceipt; if (!frozen) throw new Error('Check the current closure request first.');
    const target = {workspace_id:frozen.scope.workspace_id,request_id:frozen.request_id};
    try {
      const row = await api(`${base}/workspaces/${target.workspace_id}/closures/${target.request_id}/reconcile-local`,'POST',{expected_revision:frozen.revision});
      validateReceipt(row,target); renderReceipt(row);
    } catch(error) {
      if (![401,403,404,422].includes(error.status)) { await status(target); return; }
      throw error;
    }
  });
  $('closure-logout').onclick = () => guarded(async()=>{ signedOut(); await api(base+'/session','DELETE'); $('closure-message').textContent = 'Signed out. Sign in again to recover this request’s current status.'; });
  $('closure-preview').onclick = () => guarded(async()=>{
    clear(); const workspace = workspaces.find(w=>String(w.id)===$('closure-workspace').value);
    if (!workspace || typeof workspace.name !== 'string' || !workspace.name.trim()) throw new Error('Choose a named workspace you own.');
    previewKey ||= crypto.randomUUID();
    const row = await api(`${base}/workspaces/${workspace.id}/closure-preview`,'POST',{},previewKey); previewKey = null;
    if (row.scope.workspace_id !== workspace.id || !/^[a-f0-9]{64}$/.test(row.inventory_digest)) throw new Error('Invalid preview. Request a fresh review.');
    preview = row; previewName = workspace.name;
    $('closure-target').textContent = `${workspace.name} · Workspace ${workspace.id}`;
    $('closure-digest').textContent = `Revision ${row.revision} · ${row.inventory_digest}`;
    $('closure-preview-receipt').href = link(row); displayBlockers('closure-preview-blockers',row.blockers || []);
    const labels = {campaigns:'Imported Campaigns',customer_goals:'Saved Goals',customer_media_objects:'Private Media Objects',publication_receipts:'Publication Evidence Records',job_runs:'Background Job Records'};
    for (const section of row.inventory.sections) if (labels[section.table] && section.count !== null) $('closure-inventory').append(text('p',`${labels[section.table]}: ${section.count} retained`));
    $('closure-review').hidden = false; $('closure-message').textContent = 'Review the effects and exact workspace before confirming.';
  });
  $('closure-confirm-form').onsubmit = event => { event.preventDefault(); const accepted = preview && $('closure-name').value === previewName && $('closure-ack').checked;
    guarded(async()=>{
      if (!accepted || !preview) throw new Error('Type the exact workspace name and acknowledge the effects.');
      const frozen = preview, target = {workspace_id:frozen.scope.workspace_id,request_id:frozen.request_id};
      history.replaceState(null,'',link(frozen)); clear(); $('closure-selection').hidden = true;
      try {
        const row = await api(`${base}/workspaces/${target.workspace_id}/closures/${target.request_id}/confirm`,'POST',{expected_revision:frozen.revision,inventory_digest:frozen.inventory_digest,confirm_workspace_id:target.workspace_id});
        validateReceipt(row,target); renderReceipt(row);
      } catch (error) {
        // A response may be lost after commit. Reauthorize/read the dedicated status
        // route before claiming success or inviting another mutation.
        if (![401,403,404,409,422].includes(error.status)) { await status(target); return; }
        throw error;
      }
    });
  };
  window.addEventListener('pageshow',event=>{ if(event.persisted) guarded(session); });
  window.addEventListener('popstate',()=>guarded(session));
  guarded(session);
}
