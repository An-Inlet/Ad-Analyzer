const params = new URLSearchParams(location.search);
history.replaceState(null, '', location.pathname);
const result = document.getElementById('tiktok-result'), panel = document.getElementById('tiktok-selection');
const account = document.getElementById('tiktok-account'), select = document.getElementById('tiktok-select');
const returned = document.getElementById('tiktok-return');
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
    const data = await post(`/api/customer/v1/workspaces/${pending.workspace_id}/sources/tiktok_ads/select`, {state:pending.state, external_id:account.value});
    if (data.workspace_id !== pending.workspace_id) throw new Error('Workspace unavailable. Return to Inlet.');
    pending = null; location.replace(returned.href);
  } catch(error) { failed(error); }
};
if (params.has('error')) result.textContent = 'TikTok authorization was not completed. Return to Inlet to try again.';
else if (params.getAll('state').length !== 1 || params.has('code') || params.getAll('auth_code').length !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(params.get('state') || '')) result.textContent = 'No valid callback. Return to Inlet to start or retry.';
else {
  const state = params.get('state');
  post('/api/customer/v1/sources/tiktok_ads/callback', {state, code:params.get('auth_code')}).then(data => {
    if (!Number.isSafeInteger(data.workspace_id) || data.workspace_id < 1 || !Array.isArray(data.accounts)) throw new Error('Account discovery unavailable. Restart connection.');
    returned.href = '/app?workspace=' + data.workspace_id;
    const available = data.accounts.filter(row => /^\d{1,32}$/.test(row.external_id) && row.currency && row.time_zone);
    if (!available.length) { result.textContent = 'No supported advertisers with currency and time zone were returned. Return to Inlet to try another TikTok login.'; return; }
    pending = {state, workspace_id:data.workspace_id};
    account.replaceChildren();
    for (const row of available) { const option = document.createElement('option'); option.value = row.external_id; option.textContent = `${row.name} · ${row.external_id} · ${row.currency} · ${row.time_zone}`; account.append(option); }
    panel.hidden = false; result.textContent = 'Choose the advertiser account to connect to this workspace.';
  }).catch(failed);
}
