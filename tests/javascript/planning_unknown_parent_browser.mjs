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
const catalogs = [], mutations = [], catalogResponses = [];
window.fetch = async (...args) => {
  const response = await realFetch(...args), path = String(args[0]);
  if (path.endsWith('/target-catalog-v2')) {
    const body = await response.clone().json(); catalogResponses.push({status: response.status, body});
    if (response.ok) catalogs.push(body);
  }
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
const child = catalog => {
  const targets = catalog.targets.filter(target => target.entity.kind !== 'campaign');
  assert(targets.length === 1, 'one exact native child in this bounded fixture');
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
const state = () => read('/__fixture__/topology-state');
const exactState = (a, b, message) => assert(same(a, b), message);
try {
  const signed = await fetch('/api/customer/v1/session', {method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-Inlet-Request': '1'},
    body: JSON.stringify({id_token: 'goal-progress:unknown-parent'})});
  assert(signed.ok, 'actual sign in');
  await import('/app/assets/planning.mjs');
  await until(() => settled() && $('workspace').options.length > 1, 'workspaces');
  change('workspace', String(inputs.workspace_id));
  await until(() => settled() && !$('new').hidden, 'owned workspace');
  $('new').click(); await until(() => settled() && !$('editor').hidden, 'new editor');
  change('goal', inputs.goal.goal_id);
  const account = [...$('accounts').querySelectorAll('input')].find(node => node.value === String(inputs.accounts[0].account_id));
  assert(account, 'owned exact account'); account.checked = true; account.dispatchEvent(new Event('change'));
  $('milestone').value = 'Review exact child topology and original history';
  $('start').value = inputs.reporting_window.starts_at.slice(0, 16);
  $('end').value = inputs.reporting_window.ends_at_exclusive.slice(0, 16);
  $('targets-read').click(); await until(() => settled() && catalogs.length === 1, 'original read');
  const original = child(catalogs[0]), oldParent = inputs.accounts[0].platform === 'google_ads' ? '1' : '5';
  assert(original.entity.reference.parent_campaign_id === oldParent, 'original exact parent');
  assert(catalogs[0].targets.some(t => t.entity.kind === 'campaign' && t.entity.reference.entity_id === oldParent), 'parent actually observed');
  allocate(original); $('save').click();
  await until(() => settled() && $('editor').hidden, 'saved original child selector');
  assert(mutations.length === 1 && same(mutations[0].inputs.fixed_allocations[0].target, selector(original)), 'original exact UI request');
  $('generate').click(); await until(() => settled() && $('document').textContent.includes('Plan Version 1'), 'original generation');
  const root = '/api/customer/v1/workspaces/' + inputs.workspace_id + '/planning/plans';
  const listing = await read(root); assert(listing.items.length === 1, 'one plan');
  const path = root + '/' + listing.items[0].plan_id;
  const v1 = await read(path), originalExport = await read(path + '/export?version=1');
  const oldTarget = v1.document.inputs.fixed_allocations[0].target;
  assert(oldTarget.provider_reference.entity_id === original.entity.reference.entity_id && oldTarget.provider_reference.parent_campaign_id === oldParent, 'saved child and original parent');
  assert(same(oldTarget.account, inputs.accounts[0]), 'exact owned full account reference');
  assert(originalExport.document_digest === v1.document_digest, 'original export digest');
  $('edit').click(); await until(() => settled() && !$('editor').hidden, 'edit before orphan');
  const beforeOrphan = await state();
  await phase('orphan'); $('targets-read').click();
  await until(() => settled() && catalogResponses.length === 2, 'orphan read completed');
  const refused = catalogResponses[1];
  const fixedError = 'Account diagnostics could not be completed. Check your connection and try again.';
  assert(refused.status === 409 && refused.body.detail === fixedError, 'actual generic topology refusal');
  const visibleFailure = $('message').textContent;
  assert(visibleFailure.includes('The plan, source or selected snapshot changed. Read the current plan and review your inputs.'), 'visible read failure: ' + visibleFailure);
  assert(catalogs.length === 1 && !$('targets').querySelector('[data-role="target-choice"]'), 'no partial catalog or stale controls');
  exactState(await state(), beforeOrphan, 'failed read preserves complete receipt and planning graph');
  $('replace-targets').checked = true; $('save').click();
  await until(() => settled() && $('message').textContent.includes('Read targets again before saving'), 'failed read requires fresh targets even with confirmation');
  assert(mutations.length === 1, 'orphan save never submits implicit old or empty choices');
  const afterOrphan = await state(); exactState(afterOrphan, beforeOrphan, 'failed save preserves complete graph');
  $('cancel').click(); assert($('editor').hidden, 'cancel failed draft');
  assert(same((await read(path)).document, v1.document), 'original as-of current document after orphan');
  assert(same((await read(path + '/versions/1')).document, v1.document), 'original history after orphan');
  assert(same(await read(path + '/export?version=1'), originalExport), 'original complete export after orphan');

  await phase('recovered'); $('edit').click();
  await until(() => settled() && !$('editor').hidden, 'recovery edit');
  $('targets-read').click(); await until(() => settled() && catalogs.length === 2, 'fresh recovered read');
  const recovered = child(catalogs[1]);
  assert(recovered.entity.reference.entity_id === original.entity.reference.entity_id && recovered.entity.name === original.entity.name, 'same child ID and display name');
  assert(recovered.entity.reference.advertiser_id === original.entity.reference.advertiser_id && recovered.entity.reference.platform === original.entity.reference.platform, 'same owned advertiser and platform');
  assert(recovered.entity.reference.parent_campaign_id === '9' && catalogs[1].targets.some(t => t.entity.kind === 'campaign' && t.entity.reference.entity_id === '9'), 'actual recovered parent in catalog');
  assert(catalogs[1].targets.every(t => t.entity.reference.entity_id !== oldParent), 'old parent no longer in fresh catalog');
  assert(recovered.canonical_entity_key === original.canonical_entity_key && recovered.selection_key !== original.selection_key, 'stable child identity, changed snapshot selector');
  const host = field(recovered); assert(host, 'exact recovered child control');
  assert(host.querySelector('[data-role="target-choice"]').value === 'include' && host.querySelector('[data-role="target-amount"]').value === '', 'no old fixed allocation copied');
  assert(!$('replace-targets').checked, 'no automatic confirmation after recovery');
  const beforeConfirmation = await state();
  $('save').click(); await until(() => settled() && $('message').textContent.includes('explicitly confirm'), 'recovery requires explicit confirmation');
  assert(mutations.length === 1, 'no name or stable-ID automatic reassignment');
  exactState(await state(), beforeConfirmation, 'unconfirmed recovery leaves graph unchanged');
  allocate(recovered); $('replace-targets').checked = true; $('save').click();
  await until(() => settled() && $('editor').hidden, 'explicit recovery saved');
  assert(mutations.length === 2 && same(mutations[1].inputs.fixed_allocations[0].target, selector(recovered)), 'exact fresh UI selector');
  $('generate').click(); await until(() => settled() && $('document').textContent.includes('Plan Version 2'), 'recovered generation');
  const v2 = await read(path), newTarget = v2.document.inputs.fixed_allocations[0].target;
  assert(same(newTarget.account, oldTarget.account), 'full owned account preserved');
  assert(newTarget.provider_reference.entity_id === original.entity.reference.entity_id && newTarget.provider_reference.parent_campaign_id === '9', 'exact new child parent retained');
  assert(newTarget.canonical_entity_key === recovered.canonical_entity_key && newTarget.selection_key === recovered.selection_key, 'exact recovered selection persisted');
  assert(v2.document.inputs.fixed_allocations[0].amount_micros === 1 && v2.document.parent_digest === v1.document_digest, 'allocation and immutable parent lineage');
  const historical = await read(path + '/versions/1'), oldExport = await read(path + '/export?version=1');
  assert(same(historical.document, v1.document) && historical.document_digest === v1.document_digest, 'exact historical document and digest after successor');
  assert(same(oldExport.document, originalExport.document) && oldExport.document_digest === originalExport.document_digest, 'exact exported document and digest after successor');
  assert(originalExport.input_revision === 1 && originalExport.freshness === 'current', 'original export currentness');
  for (const wrapper of [historical, oldExport]) {
    assert(wrapper.version === 1 && wrapper.input_revision === 2 && wrapper.freshness === 'input_changed', 'historical wrapper has current input revision and honest freshness');
    assert(same(wrapper.inputs, v2.inputs) && same(wrapper.reasons, ['Current plan inputs differ from this version.']), 'historical wrapper preserves exact current inputs and reason');
  }
  assert(catalogResponses.length === 3 && catalogs.length === 2 && catalogResponses[0].status === 200 && catalogResponses[2].status === 200, 'two successful reads and one explicit refusal');
  await realFetch('/__fixture__/result', {method: 'POST', body: JSON.stringify({status: 'passed',
    catalogs, catalogResponses, mutations, beforeOrphan, afterOrphan, beforeConfirmation,
    v1, original_export: originalExport, v2, historical, old_export: oldExport})});
} catch (error) {
  await realFetch('/__fixture__/result', {method: 'POST', body: JSON.stringify({status: 'failed', message: error.message, stack: error.stack})});
}
