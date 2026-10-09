const inputs = __INPUTS__;
const $ = id => document.getElementById('planning-' + id);
const assert = (value, message) => { if (!value) throw Error(message); };
const until = async (fn, message) => {
  const end = Date.now() + 15000;
  while (!fn()) {
    if (Date.now() > end) throw Error(message + ' · ' + $('message').textContent);
    await new Promise(resolve => setTimeout(resolve, 20));
  }
};
const settled = () => !$('list-refresh').disabled;
const change = (id, value) => { $(id).value = value; $(id).dispatchEvent(new Event('change')); };
const realFetch = window.fetch.bind(window);
const catalogs = [], mutations = [];
window.fetch = async (...args) => {
  const response = await realFetch(...args), path = String(args[0]);
  if (path.endsWith('/target-catalog-v2') && response.ok) catalogs.push(await response.clone().json());
  if (args[1]?.method === 'POST' && (/\/planning\/plans$/.test(path) || path.endsWith('/inputs'))) {
    mutations.push(JSON.parse(args[1].body));
  }
  return response;
};
const read = async path => {
  const response = await realFetch(path);
  assert(response.ok, 'owned read: ' + path + ' status ' + response.status);
  return response.json();
};
const campaign = catalog => {
  const targets = catalog.targets.filter(target => target.entity.kind === 'campaign');
  assert(targets.length === 1, 'one exact native campaign in this bounded fixture');
  return targets[0];
};
const field = target => $('targets').querySelector(`[data-target-key="${CSS.escape(target.canonical_entity_key)}"]`);
const selector = target => ({account_id: inputs.accounts[0].account_id,
  canonical_entity_key: target.canonical_entity_key, selection_key: target.selection_key});
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const allocate = target => {
  const host = field(target); assert(host, 'exact canonical target control');
  const choice = host.querySelector('[data-role="target-choice"]');
  choice.value = 'fixed'; choice.dispatchEvent(new Event('change'));
  const amount = host.querySelector('[data-role="target-amount"]');
  amount.value = '0.000001'; amount.dispatchEvent(new Event('input'));
};
const phase = async value => {
  const response = await realFetch('/__fixture__/inventory/' + value, {method: 'POST'});
  assert(response.ok, 'closed fixture phase ' + value);
  assert((await response.json()).phase === value, 'phase applied');
};
try {
  const signed = await fetch('/api/customer/v1/session', {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Inlet-Request': '1'},
    body: JSON.stringify({id_token: 'goal-progress:target-disappearance'})});
  assert(signed.ok, 'actual sign in');
  await import('/app/assets/planning.mjs');
  await until(() => settled() && $('workspace').options.length > 1, 'workspaces');
  change('workspace', String(inputs.workspace_id));
  await until(() => settled() && !$('new').hidden, 'owned workspace');
  $('new').click(); await until(() => settled() && !$('editor').hidden, 'new editor');
  change('goal', inputs.goal.goal_id);
  const account = [...$('accounts').querySelectorAll('input')].find(node => node.value === String(inputs.accounts[0].account_id));
  assert(account, 'owned exact account'); account.checked = true; account.dispatchEvent(new Event('change'));
  $('milestone').value = 'Review exact disappeared and replacement targets';
  $('start').value = inputs.reporting_window.starts_at.slice(0, 16);
  $('end').value = inputs.reporting_window.ends_at_exclusive.slice(0, 16);
  $('targets-read').click(); await until(() => settled() && catalogs.length === 1, 'original read');
  const original = campaign(catalogs[0]), oldId = inputs.accounts[0].platform === 'google_ads' ? '1' : '5';
  assert(original.entity.reference.entity_id === oldId, 'original native campaign');
  assert(typeof original.entity.name === 'string' && original.entity.name.length > 0, 'original display name exists');
  allocate(original); $('save').click();
  await until(() => settled() && $('editor').hidden, 'saved original exact selector');
  assert(mutations.length === 1 && same(mutations[0].inputs.fixed_allocations[0].target, selector(original)), 'original exact UI request');
  const root = '/api/customer/v1/workspaces/' + inputs.workspace_id + '/planning/plans';
  const listing = await read(root); assert(listing.items.length === 1, 'one plan');
  const path = root + '/' + listing.items[0].plan_id;

  await phase('absent'); $('edit').click();
  await until(() => settled() && !$('editor').hidden, 'edit before absence');
  $('targets-read').click(); await until(() => settled() && catalogs.length === 2, 'fresh disappearance read');
  assert(catalogs[1].targets.length === 0, 'actual empty native inventory');
  assert(!$('targets').querySelector('[data-role="target-choice"]'), 'no old target control');
  assert($('targets').textContent.includes('No targets were returned within the reported coverage'), 'honest empty coverage');
  assert(!$('replace-targets').checked, 'removal not automatically confirmed');
  $('save').click(); await until(() => settled() && $('message').textContent.includes('explicitly confirm'), 'unconfirmed empty replacement denied');
  assert(mutations.length === 1, 'no silent removal save');
  $('cancel').click(); assert($('editor').hidden, 'cancel draft');
  $('generate').click(); await until(() => settled() && $('document').textContent.includes('Plan Version 1'), 'original as-of generation');
  const v1 = await read(path), oldTarget = v1.document.inputs.fixed_allocations[0].target;
  assert(oldTarget.provider_reference.entity_id === oldId && oldTarget.selection_key === original.selection_key && oldTarget.canonical_entity_key === original.canonical_entity_key, 'original receipt retained despite fresh absence');
  const artifact = await read(path + '/export?version=1');
  assert(artifact.document_digest === v1.document_digest, 'original artifact digest');

  await phase('replacement'); $('edit').click();
  await until(() => settled() && !$('editor').hidden, 'replacement edit');
  $('targets-read').click(); await until(() => settled() && catalogs.length === 3, 'fresh replacement read');
  const replacement = campaign(catalogs[2]);
  assert(replacement.entity.name === original.entity.name && replacement.entity.reference.entity_id === '9', 'same name different native identity');
  assert(replacement.entity.reference.advertiser_id === original.entity.reference.advertiser_id, 'same owned advertiser');
  assert(replacement.canonical_entity_key !== original.canonical_entity_key && replacement.selection_key !== original.selection_key, 'distinct exact replacement selectors');
  assert(catalogs[2].targets.every(target => target.entity.reference.entity_id !== oldId), 'old campaign absent');
  assert(catalogs[2].targets.filter(target => target.entity.kind !== 'campaign').every(target => target.entity.reference.parent_campaign_id === '9'), 'actual child parents follow replacement where present');
  const host = field(replacement); assert(host && host.querySelector('legend').textContent.includes('campaign · 9'), 'visible native identity');
  assert(host.querySelector('[data-role="target-choice"]').value === 'include' && host.querySelector('[data-role="target-amount"]').value === '', 'no copied fixed allocation');
  assert(!$('replace-targets').checked, 'replacement confirmation remains explicit');
  $('save').click(); await until(() => settled() && $('message').textContent.includes('explicitly confirm'), 'unconfirmed replacement denied');
  assert(mutations.length === 1, 'no name-only remap mutation');
  allocate(replacement); $('replace-targets').checked = true; $('save').click();
  await until(() => settled() && $('editor').hidden, 'explicit replacement save');
  assert(mutations.length === 2 && mutations[1].inputs.fixed_allocations[0].amount_micros === 1 && same(mutations[1].inputs.fixed_allocations[0].target, selector(replacement)), 'exact explicit replacement request');
  $('generate').click(); await until(() => settled() && $('document').textContent.includes('Plan Version 2'), 'replacement version');
  const v2 = await read(path), newTarget = v2.document.inputs.fixed_allocations[0].target;
  assert(newTarget.provider_reference.entity_id === '9' && newTarget.selection_key === replacement.selection_key && newTarget.canonical_entity_key === replacement.canonical_entity_key, 'new native ID persisted');
  const historical = await read(path + '/versions/1'), oldExport = await read(path + '/export?version=1');
  assert(same(historical.document, v1.document) && oldExport.document_digest === artifact.document_digest, 'immutable original history and artifact');
  assert(catalogs.length === 3, 'three explicit catalog reads only');
  await realFetch('/__fixture__/result', {method: 'POST', body: JSON.stringify({status: 'passed',
    original_selector: selector(original), replacement_selector: selector(replacement),
    original_native_id: oldId, replacement_native_id: '9', display_name: original.entity.name,
    original_expires_at: catalogs[0].expires_at, replacement_expires_at: catalogs[2].expires_at,
    version1_digest: v1.document_digest, version2_digest: v2.document_digest,
    save_requests: mutations.length, catalog_reads: catalogs.length})});
} catch (error) {
  await realFetch('/__fixture__/result', {method: 'POST', body: JSON.stringify({status: 'failed', message: error.message, stack: error.stack})});
}
