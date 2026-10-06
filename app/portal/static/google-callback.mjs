const params = new URLSearchParams(location.search);
history.replaceState(null, '', location.pathname);
const result = document.getElementById('google-result'), panel = document.getElementById('google-selection');
const account = document.getElementById('google-account'), select = document.getElementById('google-select');
const returned = document.getElementById('google-return');
let pending = null;
const csrf = () => document.cookie.split(';').map(x => x.trim()).find(x => x.startsWith('__Host-inlet_csrf='))?.split('=')[1] || '';
async function post(path, body) {
  const response = await fetch(path, {method:'POST', credentials:'same-origin', redirect:'error', cache:'no-store', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf()}, body:JSON.stringify(body)});
  if (!response.ok) throw new Error('Connection unavailable or your session changed. Return to Inlet and restart.');
  return response.json();
}
function failed(error) { pending = null; panel.hidden = true; account.replaceChildren(); result.textContent = error.message; }
addEventListener('pageshow', event => { if (event.persisted) failed(new Error('This selection page was restored. Return to Inlet and restart.')); });
select.onclick = async () => {
  if (!pending || !account.value) return;
  select.disabled = true; account.disabled = true;
  try {
    const data = await post(`/api/customer/v1/workspaces/${pending.workspace_id}/google/select`, {state:pending.state, external_account_id:account.value});
    if (data.workspace_id !== pending.workspace_id) throw new Error('Workspace unavailable. Return to Inlet.');
    pending = null; location.replace(returned.href);
  } catch(error) { failed(error); }
};
if (params.has('error')) result.textContent = 'Google authorization was not completed. Return to Inlet to try again.';
else if (params.getAll('state').length !== 1 || params.getAll('code').length !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(params.get('state') || '')) result.textContent = 'No valid callback. Return to Inlet to start or retry.';
else {
  const state = params.get('state');
  post('/api/customer/v1/google/callback', {state, code:params.get('code')}).then(data => {
    if (!Number.isSafeInteger(data.workspace_id) || data.workspace_id < 1 || !Array.isArray(data.accounts)) throw new Error('Account discovery unavailable. Restart connection.');
    returned.href = '/app?workspace=' + data.workspace_id;
    const available = data.accounts.filter(row => row.manager === false && /^\d{10}$/.test(row.external_id));
    if (!available.length) { result.textContent = 'No supported advertiser accounts were returned. Manager accounts cannot be connected directly. Return to Inlet to try another Google login.'; return; }
    pending = {state, workspace_id:data.workspace_id};
    account.replaceChildren();
    for (const row of available) { const option = document.createElement('option'); option.value = row.external_id; option.textContent = `${row.name} · ${row.external_id} · ${row.currency} · ${row.time_zone}`; account.append(option); }
    panel.hidden = false; result.textContent = 'Choose the advertiser account to connect to this workspace.';
  }).catch(failed);
}
