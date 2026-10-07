const $ = id => document.getElementById(id);
let epoch = 0, user = null, workspace = '', requestId = null, pendingKey = null;
const say = message => { $('export-message').textContent = message; };
const root = () => `/api/customer/v1/workspaces/${workspace}/exports`;
function clearReceipt() {
  requestId = null;
  $('export-receipt').hidden = true;
  for (const id of ['export-reference', 'export-state', 'export-snapshot']) $(id).textContent = '';
  $('export-download').hidden = true;
  $('export-download').removeAttribute('href');
}
function reset() {
  epoch++; user = null; workspace = ''; pendingKey = null;
  clearReceipt(); $('export-controls').hidden = true;
  $('export-workspace').replaceChildren(new Option('Select A Workspace', ''));
  $('export-create').disabled = true;
}
async function api(path, method = 'GET', key = null) {
  const version = epoch;
  const headers = {'Accept': 'application/json'};
  if (method === 'POST') {
    const csrf = document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith('__Host-inlet_csrf='))?.split('=')[1];
    if (!/^[A-Za-z0-9_-]{43}$/.test(csrf || '')) throw new Error('Sign in again before requesting an export.');
    headers['X-CSRF-Token'] = csrf; headers['Content-Type'] = 'application/json'; headers['Idempotency-Key'] = key;
  }
  const response = await fetch(path, {method, headers, ...(method === 'POST' ? {body: '{}'} : {}), credentials: 'same-origin', redirect: 'error', cache: 'no-store'});
  if (version !== epoch) throw new Error('Workspace changed. Check your session again.');
  if (!response.ok) {
    if ([401, 403, 404].includes(response.status)) reset();
    throw new Error(({401: 'Your session ended. Sign in from your workspace.', 403: 'Only a current workspace owner can export.', 404: 'This export is unavailable to your current account.', 409: 'Export is busy or cannot be built. Refresh its status before trying again.', 429: 'Export capacity is busy. Try again later.', 503: 'Customer exports are temporarily unavailable.'})[response.status] || 'Export request failed. You can retry this request.');
  }
  const result = await response.json();
  if (version !== epoch) throw new Error('Workspace changed. Check your session again.');
  return result;
}
async function sameUser() {
  const session = await api('/api/customer/v1/session');
  if (session.user_id !== user) { reset(); history.replaceState(null, '', '/app/workspace-export'); throw new Error('Your signed-in account changed. Check your session again.'); }
}
function render(row) {
  if (row.workspace_id !== Number(workspace) || !/^[a-f0-9]{32}$/.test(row.request_id)) throw new Error('Export scope did not match.');
  requestId = row.request_id;
  $('export-reference').textContent = `Request ${requestId}`;
  $('export-state').textContent = ({requested: 'Ready To Build', building: 'Building An Archive', archive_built: 'Archive Generated · Delivery Unconfirmed', interrupted: 'Build Interrupted · No Complete Archive Produced'})[row.state] || 'Status Unavailable';
  const snapshot = row.snapshot?.find(item => item.code === 'export_snapshot');
  $('export-snapshot').textContent = snapshot ? `Snapshot ${snapshot.snapshot_revision} · ${snapshot.snapshot_as_of}. Supported data: ${snapshot.supported_customer_data_complete ? 'Complete' : 'Incomplete'}. Media: ${snapshot.media_archive_complete ? 'Complete' : 'Incomplete'}. All stored records: ${snapshot.all_stored_workspace_data_complete ? 'Complete' : 'Incomplete'}. Review the archive manifest for details.` : 'No generated snapshot recorded yet.';
  $('export-download').href = `${root()}/${requestId}/download`;
  $('export-download').hidden = row.state === 'building';
  $('export-receipt').hidden = false;
}
async function load() {
  reset();
  const session = await api('/api/customer/v1/session');
  user = session.user_id;
  const rows = await api('/api/customer/v1/workspaces');
  for (const row of rows.filter(item => item.role === 'owner')) $('export-workspace').append(new Option(row.name, row.id));
  $('export-controls').hidden = false;
  say('Choose a workspace you own.');
  const query = new URLSearchParams(location.search);
  const wid = query.get('workspace'), rid = query.get('request');
  if (/^[1-9]\d*$/.test(wid || '') && /^[a-f0-9]{32}$/.test(rid || '')) {
    workspace = wid;
    render(await api(`${root()}/${rid}`));
    say('Showing your saved export request, including a locally closing workspace when authorized.');
  }
}
async function guarded(task) {
  try { await task(); } catch (error) { say(error.message); }
}
$('export-workspace').addEventListener('change', () => {
  epoch++; clearReceipt(); pendingKey = null; workspace = $('export-workspace').value;
  $('export-create').disabled = !workspace;
});
$('export-session').addEventListener('click', () => guarded(load));
$('export-create').addEventListener('click', () => guarded(async () => {
  $('export-create').disabled = true;
  try {
    await sameUser();
    pendingKey ||= crypto.randomUUID();
    const row = await api(root(), 'POST', pendingKey);
    render(row); pendingKey = null;
    history.replaceState(null, '', `/app/workspace-export?workspace=${workspace}&request=${requestId}`);
    say('Request ready. Build and download the archive, then refresh its status.');
  } finally { $('export-create').disabled = !workspace; }
}));
$('export-refresh').addEventListener('click', () => guarded(async () => {
  await sameUser();
  render(await api(`${root()}/${requestId}`));
}));
$('export-download').addEventListener('click', () => say('Download requested. Generation and delivery are separate; refresh status when your browser finishes.'));
guarded(load);
