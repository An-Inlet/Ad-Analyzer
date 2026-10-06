const query = [...new URLSearchParams(location.search).entries()];
history.replaceState(null, '', location.pathname);
const result = document.getElementById('result'), cancel = document.getElementById('cancel-attempt');
const returnLink = document.getElementById('return-workspace');
const state = query.filter(([key]) => key === 'state');
const csrf = () => document.cookie.split(';').map(x => x.trim()).find(x => x.startsWith('__Host-inlet_csrf='))?.split('=')[1] || '';
async function post(path, body) {
  const response = await fetch(path, {method:'POST', credentials:'same-origin', redirect:'error', cache:'no-store', headers:{'Content-Type':'application/json', 'X-CSRF-Token':csrf()}, body:JSON.stringify(body)});
  if (!response.ok) throw new Error('Connection unavailable or your session changed. Return to Inlet and start again.');
  return response.json();
}
function returned(data) {
  if (!Number.isSafeInteger(data.workspace_id) || data.workspace_id < 1) throw new Error('Workspace unavailable. Return to Inlet.');
  returnLink.href = '/app?workspace=' + data.workspace_id;
  return returnLink.href;
}
if (query.some(([key]) => key === 'error')) {
  // Untrusted consent errors only affect display. Cancellation requires an explicit,
  // CSRF-protected action against this session's current stored nonce.
  result.textContent = 'Shopify authorization was not completed. Cancel this attempt, or return to Inlet to try again.';
  cancel.hidden = state.length !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(state[0][1]);
  cancel.onclick = async () => {
    cancel.disabled = true;
    try { const data = await post('/api/customer/v1/shopify/cancel', {state:state[0][1]}); returned(data); result.textContent = 'Connection attempt canceled. You can return to Inlet and try again.'; cancel.hidden = true; }
    catch (error) { result.textContent = error.message; }
  };
} else if (!query.length) {
  result.textContent = 'No active authorization callback. Return to Inlet to start or retry.';
} else {
  post('/api/customer/v1/shopify/callback', {query})
    .then(data => { result.textContent = 'Store connected. Returning to your workspace…'; location.replace(returned(data)); })
    .catch(error => { result.textContent = error.message; });
}
