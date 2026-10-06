const $ = id => document.getElementById(id);
let epoch = 0, user = null;
class Stale extends Error {}
const say = text => { $('activity-message').textContent = text; };
function clear() { $('activity-items').replaceChildren(); $('activity-coverage').textContent = ''; }
function reset() {
  epoch++; user = null; clear(); $('activity-controls').hidden = true;
  $('activity-workspace').replaceChildren(new Option('Select A Workspace', ''));
  $('activity-refresh').disabled = true;
}
async function api(path, turn) {
  const cookies = document.cookie;
  let response;
  try { response = await fetch(path, {credentials: 'same-origin', cache: 'no-store', redirect: 'error', headers: {Accept: 'application/json'}}); } catch (error) { if (turn !== epoch) throw new Stale(); throw new Error('Activity is unavailable. Try again later.'); }
  if (turn !== epoch) throw new Stale();
  if (cookies !== document.cookie) { reset(); throw new Error('Your session changed. Check your session again.'); }
  if (!response.ok) {
    if ([401, 403, 404].includes(response.status)) reset();
    throw new Error(response.status === 401 ? 'Your session ended. Sign in from Your Workspace.' : 'Activity is unavailable. Check your session or try again later.');
  }
  let row;
  try { row = await response.json(); } catch (error) { if (turn !== epoch) throw new Stale(); throw new Error('Activity response could not be verified.'); }
  if (turn === epoch && cookies !== document.cookie) { reset(); throw new Error('Your session changed. Check your session again.'); }
  if (turn !== epoch) throw new Stale();
  return row;
}
const labels = {
  goal: {saved: 'Goal Revision Saved', confirmed: 'Goal Revision Confirmed'},
  campaign: {saved: 'Campaign Revision Saved', approved: 'Campaign Revision Approved'},
  provider_receipt: {verified_effect: 'Provider Effect Verified', verified_target_state: 'Provider Target State Verified', verified_no_effect: 'No Provider Effect Verified', unknown: 'Provider Outcome Unknown — Review Required', conflict: 'Provider Evidence Conflicts — Review Required'},
};
async function refresh() {
  const turn = ++epoch, workspace = $('activity-workspace').value;
  clear();
  if (!workspace) { say('Choose a workspace.'); return; }
  $('activity-refresh').disabled = true;
  try {
    const session = await api('/api/customer/v1/session', turn);
    if (session.user_id !== user) { reset(); throw new Error('Your signed-in account changed. Check your session again.'); }
    const row = await api(`/api/customer/v1/workspaces/${encodeURIComponent(workspace)}/activity`, turn);
    if (row.workspace_id !== Number(workspace) || row.schema_version !== 'inlet.customer.activity.v1' || !Array.isArray(row.items) || row.items.length > 90) throw new Error('Activity response could not be verified.');
    // Recheck after the history response, before exposing it after an account switch.
    const current = await api('/api/customer/v1/session', turn);
    if (current.user_id !== user) { reset(); throw new Error('Your signed-in account changed. Check your session again.'); }
    const nodes = row.items.map(item => {
      const label = labels[item.source]?.[item.event];
      if (!label || !Number.isFinite(Date.parse(item.recorded_at))) throw new Error('Activity response could not be verified.');
      const li = document.createElement('li');
      li.textContent = `${label}${Number.isSafeInteger(item.revision) ? ` · Revision ${item.revision}` : ''} · ${new Date(item.recorded_at).toISOString()}${item.source === 'provider_receipt' ? (item.environment === 'contract_test' ? ' · Offline Contract Test' : item.environment === 'live' ? ' · Live Provider Evidence' : ' · Environment Unavailable') : ''}`;
      return li;
    });
    $('activity-items').replaceChildren(...nodes);
    $('activity-coverage').textContent = `${row.truncated ? 'Some older records are omitted. ' : ''}Recent goal and campaign revisions only. ${row.receipt_coverage === 'owner_only' ? 'Provider receipts are available only to the workspace owner.' : 'Only the latest receipt for each of the ten most recent provider attempts is included.'}${row.receipt_unavailable ? ' Some recent attempts have no verified readable receipt; review is required.' : ''}`;
    say(nodes.length ? 'Recorded activity loaded.' : 'No activity was found in the covered records. This does not prove no advertising activity occurred.');
  } finally { if (turn === epoch) $('activity-refresh').disabled = !workspace; }
}
async function load() {
  reset(); const turn = epoch;
  user = (await api('/api/customer/v1/session', turn)).user_id;
  const rows = await api('/api/customer/v1/workspaces', turn);
  for (const row of rows) $('activity-workspace').append(new Option(row.name, row.id));
  $('activity-controls').hidden = false; say('Choose a workspace to review recorded activity.');
}
async function guarded(task) { try { await task(); } catch (error) { if (!(error instanceof Stale)) { clear(); say(error.message); } } }
$('activity-workspace').addEventListener('change', () => guarded(refresh));
$('activity-refresh').addEventListener('click', () => guarded(refresh));
$('activity-session').addEventListener('click', () => guarded(load));
guarded(load);
