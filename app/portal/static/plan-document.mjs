import {appendReportingComparability} from './plan-reporting-comparability.mjs';
import {appendGoogleOwnerReview} from './plan-google-owner-review.mjs';
import {appendCreativeBasis} from './plan-creative-basis.mjs';
// Display-only immutable planning artifact. Authorization and source validation are server-owned.
const platforms = {google_ads: 'Google Ads', meta_ads: 'Meta Ads', tiktok_ads: 'TikTok Ads'};
const statuses = {current: 'Current Evidence', expired: 'Expired Evidence', source_changed: 'Source Changed', goal_changed: 'Goal Changed', input_changed: 'Inputs Changed'};
const title = value => String(value).replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase());
const text = (doc, tag, value) => {const node = doc.createElement(tag); node.textContent = String(value); return node;};
const stamp = value => {const date = new Date(value); if (!Number.isFinite(date.getTime())) throw new Error('Invalid plan date'); return date.toISOString();};
const money = (value, currency) => {
  if (!Number.isSafeInteger(value) || value < 0 || value > 1e15 || !/^[A-Z]{3}$/.test(currency)) throw new Error('Invalid plan amount');
  return `${currency} ${Math.floor(value / 1e6)}.${String(value % 1e6).padStart(6, '0')}`;
};
function list(doc, host, heading, values) {
  if (!Array.isArray(values) || !values.length) return;
  host.append(text(doc, 'h4', heading));
  const node = doc.createElement('ul');
  for (const value of values) node.append(text(doc, 'li', value));
  host.append(node);
}
function target(value) {
  const account = value.account, platform = platforms[account.platform];
  if (!platform) throw new Error('Unknown plan platform');
  if (!value.provider_reference) return `${platform} · Connected Account ${account.account_id}`;
  const ref = value.provider_reference;
  return `${platform} · ${value.display_name ?? 'Name Unavailable'} · ${title(value.kind)} ${ref.entity_id} · Advertiser ${ref.advertiser_id}${ref.parent_campaign_id ? ` · Parent Campaign ${ref.parent_campaign_id}` : ''}`;
}
export function clearPlanDocument(host) {host.replaceChildren(); host.hidden = true;}
export function renderPlanDocument(host, plan, {workspaceId, planId, freshness, reasons = []}, now = Date.now()) {
  clearPlanDocument(host);
  if (plan?.schema_version !== 'inlet.plan-version.v1' || plan.advertising_writes_enabled !== false || plan.spending_authority !== 'none' || plan.inputs?.workspace_id !== workspaceId || plan.inputs?.plan_id !== planId || !Number.isSafeInteger(plan.version) || plan.version < 1 || !Object.hasOwn(statuses, freshness) || plan.quality_status !== 'not_expert_qualified' || !['reviewable', 'needs_input'].includes(plan.readiness)) throw new Error('Plan response does not match the selected workspace and plan.');
  for (const [key, bound] of [['actions', 100], ['scenarios', 8], ['briefs', 30], ['evidence', 400]]) if (!Array.isArray(plan[key]) || plan[key].length > bound) throw new Error('Plan response exceeds display limits.');
  const doc = host.ownerDocument, fragment = doc.createDocumentFragment(), inputs = plan.inputs;
  const expires = Date.parse(plan.valid_until);
  if (!Number.isFinite(expires)) throw new Error('Invalid plan expiry');
  const displayFreshness = freshness === 'current' && now >= expires ? 'expired' : freshness;
  fragment.append(text(doc, 'h2', `Plan Version ${plan.version}`), text(doc, 'p', plan.summary));
  const notice = text(doc, 'p', `${statuses[displayFreshness]} · ${title(plan.readiness)}. Recommendation quality has not been expert-qualified. Customer decisions, reported application and observed provider settings are separate records.`);
  notice.setAttribute('role', 'status'); fragment.append(notice);
  fragment.append(text(doc, 'p', `Generated ${stamp(plan.generated_at)} by ${plan.generated_by}. Evidence valid until ${stamp(plan.valid_until)}. Generator ${plan.generator_version}; policy ${plan.policy_version}.`));
  fragment.append(text(doc, 'p', 'Planning Only. Inlet has not published or changed advertising from this document. Review any action before applying it yourself.'));
  list(doc, fragment, 'Freshness Details', reasons);
  list(doc, fragment, 'Unresolved Sections', plan.section_limitations);
  list(doc, fragment, 'Plan Limitations', plan.limitations);
  fragment.append(text(doc, 'h3', 'Customer Goal And Constraints'), text(doc, 'p', inputs.milestone));
  const goal = inputs.goal, definition = goal.definition, window = definition.target_window;
  fragment.append(text(doc, 'p', `Confirmed Goal Revision ${goal.revision}: ${money(definition.target_micros, window.currency)} Shopify Merchandise Net Sales. Target window ${window.start} to ${window.end} (end exclusive), ${window.time_zone}. Deadline ${definition.deadline}.`));
  const baseline = definition.baseline_window;
  fragment.append(text(doc, 'p', `Baseline window: ${baseline.start} to ${baseline.end} (end exclusive), ${baseline.time_zone}, ${baseline.currency}. This window does not by itself establish a measured baseline amount.`));
  const period = inputs.budget_period;
  fragment.append(text(doc, 'p', `Planning ceiling: ${money(inputs.total_ceiling_micros, period.currency)} · ${period.starts_on} to ${period.ends_on_exclusive} (end exclusive), ${period.time_zone}. Aggressiveness: ${title(inputs.aggressiveness)}. This ceiling is not verified remaining spend or authority to spend.`));
  if (inputs.product_offer) fragment.append(text(doc, 'p', `Customer Product Facts: ${inputs.product_offer}`));
  list(doc, fragment, 'Customer Constraints', inputs.constraints);
  list(doc, fragment, 'Customer Assumptions', inputs.assumptions.map(item => `${item.key}: ${item.statement}`));
  appendCreativeBasis(fragment,plan);
  appendGoogleOwnerReview(fragment,plan);
  appendReportingComparability(fragment,plan,{freshness:displayFreshness,now});
  fragment.append(text(doc, 'h3', 'Manual Actions'));
  for (const action of [...plan.actions].sort((a, b) => a.priority - b.priority)) {
    const section = doc.createElement('section');
    section.append(text(doc, 'h4', `${action.priority}. ${action.title}`), text(doc, 'p', target(action.target)), text(doc, 'p', `Action ${action.key} · ${title(action.kind)}`), text(doc, 'p', action.rationale));
    list(doc, section, 'Manual Steps', action.manual_steps);
    list(doc, section, 'Prerequisites', action.prerequisites);
    list(doc, section, 'Conflicts', action.conflicts);
    section.append(text(doc, 'p', `Expected Effect: ${action.expected_effect}`), text(doc, 'p', `Measurement Criterion: ${action.measurement_criterion}`));
    list(doc, section, 'Evidence References', action.evidence_keys);
    list(doc, section, 'Assumption References', action.assumption_keys);
    list(doc, section, 'Limitations', action.limitations);
    // Typed proposals retain exact units/fields, without creating a clickable execution control.
    if (action.proposed_fields.length) section.append(text(doc, 'h4', 'Proposed Field Details'), text(doc, 'pre', JSON.stringify(action.proposed_fields, null, 2)));
    section.append(text(doc, 'h4', 'Native Budget Proposal'), text(doc, 'pre', action.native_budget === null ? 'Unavailable — no native budget change proposed.' : JSON.stringify(action.native_budget, null, 2)));
    fragment.append(section);
  }
  fragment.append(text(doc, 'h3', 'Independent Budget Alternatives'), text(doc, 'p', 'Each alternative stands alone. Do not add alternatives together. Planning allocations are separate from current provider budgets.'));
  for (const scenario of plan.scenarios) {
    const section = doc.createElement('section');
    section.append(text(doc, 'h4', scenario.title), text(doc, 'p', `${title(scenario.provenance)} · Ceiling ${money(scenario.ceiling_micros, period.currency)} · Unallocated ${money(scenario.unallocated_micros, period.currency)}`));
    for (const allocation of scenario.allocations) section.append(text(doc, 'p', `${target(allocation.target)}: ${money(allocation.amount_micros, period.currency)}. ${allocation.rationale}`));
    list(doc, section, 'Scenario Assumptions', scenario.assumptions); fragment.append(section);
  }
  fragment.append(text(doc, 'h3', 'Creative Briefs'));
  if (!plan.briefs.length) fragment.append(text(doc, 'p', 'No creative brief is available in this version.'));
  for (const brief of plan.briefs) {
    const section = doc.createElement('section');
    section.append(text(doc, 'h4', brief.format), text(doc, 'p', target(brief.target)), text(doc, 'p', `Action ${brief.action_key} · Placement: ${brief.placement}`));
    for (const [heading, key] of [['Product Facts', 'product_facts'], ['Hypotheses', 'hypotheses'], ['Asset Gaps', 'asset_gaps'], ['Landing Page Constraints', 'landing_page_constraints'], ['Claim Evidence', 'claim_evidence_keys'], ['Assumption References', 'assumption_keys'], ['Hooks', 'hooks'], ['Copy Directions', 'copy_directions'], ['Visual Directions', 'visual_directions'], ['Required Assets', 'required_assets'], ['Customer Review Checklist', 'customer_review_checklist']]) list(doc, section, heading, brief[key]);
    for (const [heading, key] of [['Objective', 'objective'], ['Audience', 'audience'], ['Offer', 'offer'], ['Measurement Plan', 'measurement_plan']]) section.append(text(doc, 'p', `${heading}: ${brief[key]}`));
    fragment.append(section);
  }
  fragment.append(text(doc, 'h3', 'Evidence And Coverage'));
  for (const evidence of plan.evidence) {
    const section = doc.createElement('section');
    section.append(text(doc, 'h4', `${evidence.key} · ${title(evidence.kind)}`), text(doc, 'p', `${title(evidence.coverage)} · ${evidence.declared_scope}`), text(doc, 'p', evidence.metric_basis));
    section.append(text(doc, 'p', `Read ${stamp(evidence.observation_started_at)} to ${stamp(evidence.observed_at)}; expires ${stamp(evidence.expires_at)}. Source revision ${evidence.source_revision}; privacy revision ${evidence.privacy_revision}.`));
    if (evidence.reporting_window) section.append(text(doc, 'p', `Reporting window: ${stamp(evidence.reporting_window.starts_at)} to ${stamp(evidence.reporting_window.ends_at_exclusive)} (end exclusive).`));
    list(doc, section, 'Coverage Reasons', evidence.reasons); fragment.append(section);
  }
  host.replaceChildren(fragment); host.hidden = false;
  return {expiresAt: expires, freshness: displayFreshness};
}
