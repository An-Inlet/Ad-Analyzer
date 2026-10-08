// Customer planning hypotheses only. Server receipts remain the ownership proof.
import {renderNativeTargets} from './native-targets.mjs';

const handles = new WeakMap();
const maximumMicros = 1000000000000000n;
const text = (doc, tag, value) => {
  const node = doc.createElement(tag);
  node.textContent = value;
  return node;
};
const fail = message => { throw new Error(message); };

function micros(value) {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]{0,15})(\.[0-9]{1,6})?$/.test(value)) {
    fail('Enter a nonnegative decimal amount with at most six decimal places.');
  }
  const [whole, fraction = ''] = value.split('.');
  const amount = BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0'));
  if (amount > maximumMicros) fail('The planning allocation exceeds the supported amount.');
  return amount;
}

export function clearPlanTargetPicker(host) {
  handles.delete(host);
  host.replaceChildren();
  host.hidden = true;
}

export function renderPlanTargetPicker(host, catalog, options, onChange, now = Date.now()) {
  clearPlanTargetPicker(host);
  const {workspaceId, account, period, currency, totalCeilingMicros} = options ?? {};
  if (!Number.isFinite(now) || typeof currency !== 'string' || !/^[A-Z]{3}$/.test(currency) ||
      !Number.isSafeInteger(totalCeilingMicros) || totalCeilingMicros < 0 ||
      BigInt(totalCeilingMicros) > maximumMicros || typeof onChange !== 'function') {
    fail('Select a confirmed goal with a valid currency and spending ceiling.');
  }
  // Validate before publishing any owned DOM; copy so later caller mutation cannot
  // replace a selector or expiry in an already-rendered handle.
  const snapshot = structuredClone(catalog);
  const doc = host.ownerDocument, fragment = doc.createDocumentFragment();
  const native = doc.createElement('section');
  const expiresAt = renderNativeTargets(native, snapshot, {workspaceId, account, period}, now);
  const token = {};
  const controls = [];
  fragment.append(native, text(doc, 'h3', 'Planning Target Choices'),
    text(doc, 'p', `Fixed allocations are customer budget hypotheses in ${currency}. They are not native budget settings or permission to spend. Include is the default; no allocation is assumed.`));
  for (const target of snapshot.targets) {
    const field = doc.createElement('fieldset');
    field.dataset.targetKey = target.canonical_entity_key;
    field.append(text(doc, 'legend', `${target.entity.name ?? 'Name Unavailable'} · ${target.entity.kind} · ${target.entity.reference.entity_id}`));
    const choiceLabel = text(doc, 'label', 'Planning Choice ');
    const choice = doc.createElement('select'); choice.dataset.role = 'target-choice';
    for (const [value, label] of [['include', 'Include Without Fixed Allocation'], ['exclude', 'Exclude'], ['fixed', 'Fix Planning Allocation']]) {
      const option = text(doc, 'option', label); option.value = value; choice.append(option);
    }
    choiceLabel.append(choice);
    const amountLabel = text(doc, 'label', `Fixed Allocation (${currency}) `);
    const amount = doc.createElement('input'); amount.dataset.role = 'target-amount';
    amount.type = 'text'; amount.inputMode = 'decimal'; amount.maxLength = 23;
    amount.placeholder = '0.000000'; amount.disabled = true; amountLabel.hidden = true;
    amountLabel.append(amount);
    field.append(choiceLabel, amountLabel); fragment.append(field);
    const changed = () => { if (handles.get(host) === token) onChange(); };
    choice.addEventListener('change', () => {
      amount.disabled = choice.value !== 'fixed'; amountLabel.hidden = amount.disabled;
      changed();
    });
    amount.addEventListener('input', changed);
    controls.push({choice, amount, selector: {
      account_id: account.id,
      canonical_entity_key: target.canonical_entity_key,
      selection_key: target.selection_key,
    }});
  }
  host.replaceChildren(fragment); host.hidden = false; handles.set(host, token);
  return Object.freeze({expiresAt: snapshot.expires_at, readIntent(current = Date.now()) {
    if (handles.get(host) !== token) fail('These target choices were cleared. Read and select targets again.');
    if (!Number.isFinite(current) || current >= expiresAt) fail('These target choices expired. Read and select targets again.');
    const exclusions = [], fixed_allocations = [];
    let total = 0n;
    for (const {choice, amount, selector} of controls) {
      if (choice.value === 'exclude') exclusions.push({...selector});
      else if (choice.value === 'fixed') {
        const value = micros(amount.value); total += value;
        fixed_allocations.push({target: {...selector}, amount_micros: Number(value)});
      } else if (choice.value !== 'include') fail('Select a supported planning choice.');
    }
    if (exclusions.length > 100 || fixed_allocations.length > 100) fail('Select at most 100 exclusions and 100 fixed allocations.');
    if (total > BigInt(totalCeilingMicros)) fail('Fixed planning allocations exceed the confirmed spending ceiling.');
    return {exclusions, fixed_allocations};
  }});
}
