# Genuine Pure Creative Plan Composer V1

Depends on shared selected reporting collection and the reviewed pure creative
document contract (889c010/9a89916). Pure internal composition only: no service,
registry, repository, retained dispatch, history, UI or default activation.

Add `CreativePairedEvidenceV1` with `reporting:SelectedPairedEvidenceV1` and
`creative:CollectedCreativeBasisV1`. Its assert_ticket revalidates all values,
requires the exact canonical v5 ticket/digest, explicit selected/creative inputs,
and calls both existing reporting and private collection assertions on the same
original ticket. Exact workspace/privacy/input/order binding must survive. Require
original image observations in UTC to fall no earlier than ticket.prepared_at;
generation must be no earlier than collection/reporting/image observations. Empty
image selection remains explicit and valid. Do not substitute a v4 ticket.

Add `CreativePlanComposer.compose(*,ticket,evidence,policy,generated_at)->PlanVersion`.
Validate exact canonical policy/ticket using the shared validator, require
requires_creative=true, then revalidate/assert the paired envelope. Preserve the
existing bounded Decimal context and exception semantics. Use the original ticket,
policy and evidence to construct a genuine v5 PlanVersion once. No intermediate
v4 document, copied document tags, stripped creative fields or altered digest.

Share selected reporting action/scenario construction below the existing v4 entry
gate. A minimal private `_compose` extension accepting an optional validated
creative collection is acceptable; it must verify canonical v5 + exact ticket
binding whenever that argument is supplied. Existing v4 public compose and its
outputs stay unchanged. The v5 path skips the entire old generic creative action/
brief block instead of creating duplicate creative tasks.

For v5, derive retained proof from the private collection and append the one exact
creative:basis reference using the document helper and existing reporting deadline.
Call compose_creative_proposals with the exact inputs, current owned catalogs,
basis, canonical policy and actual customer/policy/basis reference keys/digests.
Start creative priorities after all reporting actions. Append every typed proposal
action/brief and retain the complete CreativeCompositionV1 alongside proof in the
final PlanVersion. Preserve global capacity, administrative deterministic ordering,
exclusions, missing/partial catalog limitations and unsupported-provider deferral.

Retain all creative limitations in bounded document sections, failing on capacity
or text/byte overflow rather than silently dropping/truncating evidence or guidance.
Recheck evidence/action/brief/section capacities after additions. No native budget
changes or forecast claims; production_required/not_assessed remain explicit. A
missing video witness means video production required, never proof that the entire
customer media library lacks video.

Tests build genuine canonical v5 inputs/tickets/contexts, retain exact selected and
traffic proof, and cover Meta image/TikTok storyboard, supplied/empty images,
empty/missing product, capacity0/1/unknown, exclusions, constraints, first priorities,
wrong private ticket/input/row basis, mixed/altered policy, image observation bounds
including DST, duplicate/generic creative rejection and complete output bounds.
Compare all existing v4 byte/digest golden cases unchanged. Assert v5 service
capability still refuses registration. Whole Ruff/configured mypy required.
Actual owned API generation/persistence and frozen Q03/Q04 full acceptance follow
only after atomic SQL/currentness/history wiring, not this pure composer package.
