# Standalone creative production proposals — 2026-10-11

Child of `ceea791`; implements the reviewed pure interface only. Existing
ManualAction, CreativeBrief, PlanVersion v1–v4, policy registration, APIs and
runtime files are unchanged. No v5 capability is registered; a test explicitly
proves rejection by the existing dispatcher.

`creative_composition.py` exports `compose_creative_proposals` with the approved
signature and `CreativeCompositionReferencesV1`. Its fresh canonical v5 policy
value is validated against exact policy/digest fields, not installed. The separate
`creative_production_contracts.py` deliberately has no ports/policy import; fresh
subprocess imports test this boundary for later PlanVersion integration.

Composition validates complete inputs, catalogs, basis, exact digests, account
ownership, currency and catalog privacy. Supplied catalogs and evidence keys are
unique; missing catalogs defer. Pure validation grants no ownership, currentness
or access: the future owned reader remains responsible for those facts.

Meta proposals include declared product and precision-independent price, exact
first selected source image, copy/layout/inspection/review tasks. TikTok produces
three ordered introduction/demonstration/CTA shots, factual captions, edit and
review instructions, and an explicit video-production requirement. It never
claims no video exists elsewhere. A missing demonstration fact requests
substantiation instead of inventing features. Restrictions remain verbatim in
action steps and brief copy/checklist/destination paths. All selected source images
are retained in original order, even though the first is nominated for review.

Each proposal consumes one globally confirmed finished asset. Constraints,
unknown/zero capacity, missing product, missing included campaigns or unsupported
platforms defer. Account/campaign ordering is administrative and explicitly not a
performance ranking. Exclusions apply before selection; no account fallback.
Action/brief keys and targets agree, all priorities fit MAX_ACTIONS, and no native
budget or provider fields are proposed. Text/count overflow rejects rather than
truncates. The complete canonical output additionally enforces the existing
MAX_DOCUMENT_BYTES (1,048,576 bytes), including repeated restrictions and source
references; a multi-proposal overflow regression proves refusal.

## Qualification evidence

Durable logs/JUnit: `/workspace/inlet-evidence/20261011/creative-production`.

- `pure01`: 35 passed, 0.65s, initial pure implementation.
- `pure02`: 90 passed, 0.64s, expanded composition and CreativeBasis contracts.
- `pure03`: 117 passed, 2.66s, composition/basis plus unchanged legacy composer.
- `final`: two added valid-foreign-basis/canonical-unregistered cases passed.
- `final-all`: final 46 composition cases passed, 2.57s, including complete output
  key/priority/image binding, 1MiB overflow and fresh subprocess imports.
- Final whole Ruff, configured mypy (1,374 files) and diff results are retained.
  A long test subprocess command failed Ruff E501 before being split without
  changing its command; that failed output remains retained.

Fixtures are explicitly synthetic pure contracts based on existing native catalog
fixtures. They do not establish authenticated image ownership, actual API
qualification, Q03/Q04 usefulness, visual suitability, rights, placement approval,
causal lift or delivery. No SQL/PG/live-provider operations, runtime wiring,
retention/erasure integration, public/default activation, Full, hosted CI, push or
deployment were performed. Those are separate reviewed dependencies.
