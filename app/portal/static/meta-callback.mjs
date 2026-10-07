const params = new URLSearchParams(location.search);
history.replaceState(null, '', location.pathname);
const result = document.getElementById('meta-result'), panel = document.getElementById('meta-selection');
const account = document.getElementById('meta-account'), select = document.getElementById('meta-select');
const returned = document.getElementById('meta-return');
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
    const data = await post(`/api/customer/v1/workspaces/${pending.workspace_id}/meta/select`, {state:pending.state, external_account_id:account.value, conversion_action_type:document.getElementById('meta-conversion').value});
    if (data.workspace_id !== pending.workspace_id) throw new Error('Workspace unavailable. Return to Inlet.');
    pending = null; location.replace(returned.href);
  } catch(error) { failed(error); }
};
if (params.has('error')) result.textContent = 'Meta authorization was not completed. Return to Inlet to try again.';
else if (params.getAll('state').length !== 1 || params.getAll('code').length !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(params.get('state') || '')) result.textContent = 'No valid callback. Return to Inlet to start or retry.';
else {
  const state = params.get('state');
  post('/api/customer/v1/meta/callback', {state, code:params.get('code')}).then(data => display(data, state)).catch(failed);
}
function display(data, state) {
  if (!Number.isSafeInteger(data.workspace_id) || data.workspace_id < 1 || !Array.isArray(data.accounts)) throw new Error('Account discovery unavailable. Restart connection.');
  returned.href = '/app?workspace=' + data.workspace_id;
  pending = {state, workspace_id:data.workspace_id};
  account.replaceChildren();
  for (const row of data.accounts) { const option = document.createElement('option'); option.value = row.account_id; option.textContent = `${row.name} · ${row.account_id} · ${row.currency_code} · ${row.time_zone}`; account.append(option); }
  const conversion = document.getElementById('meta-conversion');
  conversion.replaceChildren();
  for (const [value, label] of Object.entries(data.conversion_actions)) { const option = document.createElement('option'); option.value = value; option.textContent = label; conversion.append(option); }
  document.getElementById('meta-more').hidden = !data.has_more;
  panel.hidden = false; select.disabled = !data.accounts.length; account.disabled = false;
  result.textContent = data.accounts.length ? 'Choose the account and conversion event to connect.' : 'No accounts on this page. Load more if available or restart with another Meta login.';
}
document.getElementById('meta-more').onclick = async () => {
  if (!pending) return;
  const more = document.getElementById('meta-more'); more.disabled = true; select.disabled = true;
  try { const state = pending.state; const data = await post(`/api/customer/v1/workspaces/${pending.workspace_id}/meta/accounts`, {state}); display(data, state); }
  catch(error) { failed(error); } finally { more.disabled = false; }
};
