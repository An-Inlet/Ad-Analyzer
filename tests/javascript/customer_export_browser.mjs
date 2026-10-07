const originalFetch = globalThis.fetch;
const $ = id => document.getElementById(id);
const assert = (value, message) => { if (!value) throw new Error(message); };
const until = async predicate => {
  for (let count = 0; count < 200; count++) {
    if (predicate()) return;
    await new Promise(resolve => setTimeout(resolve, 10));
  }
  throw new Error('DOM condition timed out');
};
let user = 'owner-a', calls = [], failed = false;
const requestId = 'a'.repeat(32);
const row = {request_id: requestId, workspace_id: 1, state: 'requested', snapshot: []};
globalThis.fetch = async (path, options = {}) => {
  if (path === '/api/customer/v1/session') return Response.json({user_id: user});
  if (path === '/api/customer/v1/workspaces') return Response.json(user === 'owner-a' ? [{id: 1, name: 'Owned Store', role: 'owner'}] : []);
  if (path.endsWith('/exports') && options.method === 'POST') {
    calls.push(options.headers['Idempotency-Key']);
    if (!failed) { failed = true; throw new Error('Lost request response'); }
    return Response.json(row);
  }
  if (path.endsWith('/' + requestId)) return Response.json({...row, state: 'archive_built', snapshot: [{code: 'export_snapshot', snapshot_revision: 2, snapshot_as_of: '2026-10-06T00:00:00Z', supported_customer_data_complete: true, media_archive_complete: true, all_stored_workspace_data_complete: false}]});
  throw new Error('Unexpected request ' + path);
};
Object.defineProperty(document, 'cookie', {get: () => '__Host-inlet_csrf=' + 'c'.repeat(43)});
try {
  await import('/app/assets/workspace-export.mjs');
  await until(() => $('export-workspace').options.length === 2);
  $('export-workspace').value = '1';
  $('export-workspace').dispatchEvent(new Event('change'));
  $('export-create').click();
  await until(() => $('export-message').textContent.includes('Lost request response'));
  $('export-create').click();
  await until(() => !$('export-receipt').hidden);
  assert(calls.length === 2 && calls[0] === calls[1], 'Lost response changed idempotency key');
  assert($('export-download').getAttribute('href') === `/api/customer/v1/workspaces/1/exports/${requestId}/download`, 'Unsafe or incorrect download URL');
  $('export-refresh').click();
  await until(() => $('export-state').textContent.includes('Delivery Unconfirmed'));
  assert($('export-snapshot').textContent.includes('All stored records: Incomplete'), 'Missing completeness disclosure');
  user = 'owner-b';
  $('export-refresh').click();
  await until(() => $('export-message').textContent.includes('account changed'));
  assert($('export-receipt').hidden && !$('export-download').hasAttribute('href'), 'Principal change retained download');
  assert(!$('export-reference').textContent, 'Principal change retained customer content');
  $('export-session').click();
  await until(() => !$('export-controls').hidden);
  assert($('export-workspace').options.length === 1 && $('export-receipt').hidden, 'Empty workspace exposed old data');
  await originalFetch('/__result__', {method: 'POST', body: 'passed'});
} catch (error) {
  await originalFetch('/__result__', {method: 'POST', body: String(error.stack || error)});
}
