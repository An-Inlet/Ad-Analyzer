// Display-only exact successor comparison. Values may contain arbitrary customer text.
const text = (doc, tag, value) => {const node=doc.createElement(tag);node.textContent=String(value);return node;};
export function renderPlanComparison(host, comparison, expected) {
  host.replaceChildren(); host.hidden=true;
  if (comparison?.schema_version !== 'inlet.plan-version-comparison.v1' || comparison.advertising_writes_enabled !== false || comparison.spending_authority !== 'none' || comparison.decisions_carried_over !== false || comparison.semantics !== 'document_changes_not_causal_attribution' || !Array.isArray(comparison.changes) || comparison.changes.length > 500 || !Number.isSafeInteger(comparison.omitted_changes) || comparison.omitted_changes < 0) throw new Error('Plan comparison is unavailable.');
  for (const field of ['previous_version','current_version','previous_digest','current_digest']) if (comparison[field] !== expected[field]) throw new Error('Plan comparison does not match the selected versions.');
  const doc=host.ownerDocument, fragment=doc.createDocumentFragment();
  fragment.append(text(doc,'h3',`Changes From Version ${comparison.previous_version} To ${comparison.current_version}`));
  fragment.append(text(doc,'p','These are document changes. They do not establish who changed advertising or what caused a business outcome. Earlier decisions are not carried forward.'));
  if (comparison.omitted_changes) {
    const notice=text(doc,'p',`${comparison.omitted_changes} additional changes are not displayed. Review both complete versions before deciding.`);
    notice.setAttribute('role','status');fragment.append(notice);
  }
  if (!comparison.changes.length && !comparison.omitted_changes) fragment.append(text(doc,'p','No content changes. Generation time and author remain in the version headers.'));
  for (const change of comparison.changes) {
    if (!Array.isArray(change.path) || !change.path.length || change.path.length > 30 || change.path.some(p=>typeof p!=='string') || typeof change.before_present !== 'boolean' || typeof change.after_present !== 'boolean') throw new Error('Plan comparison contains an invalid change.');
    const section=doc.createElement('section');
    section.append(text(doc,'h4',change.path.join(' / ')));
    section.append(text(doc,'p','Previous Value'),text(doc,'pre',change.before_present?JSON.stringify(change.before,null,2):'Not Present'));
    section.append(text(doc,'p','Current Value'),text(doc,'pre',change.after_present?JSON.stringify(change.after,null,2):'Not Present'));
    fragment.append(section);
  }
  host.replaceChildren(fragment);host.hidden=false;
}
