# Standalone Creative Currentness V1

Prepare the read-side SQL image metadata check for later exact-v5 retained-source
wiring. No service/registry/repository/dispatch/default changes in this package.

Add `capture_creative_retained_source(db,*,principal,document,now)
 ->RetainedSourceWitness` in `creative_currentness.py`.
Require a fully validated genuine v5 document, typed proof and input bindings.
Caller owns fresh viewer identity fact and workspace-first root transaction, with
its normal final authority check. Enforce existing READ_ROLES via the same SQL-only
_guard pattern used by retained_sources, not generator identity or OWNER_ROLES.
No paid_work requirement: a permitted viewer may inspect currentness/history after
billing changes. Recheck the existing _goal revision/confirmation semantics and
workspace privacy revision before and after image locks.

Reject absent/nested/dirty transactions before queries/autoflush. Preserve exact
Session and underlying Connection root transaction identities through all reads
and guards, as the reviewed creative finalization port does. Sample strict aware
UTC max(now,database_utc_now) after lock waits and require generated_at<=time<valid_until.
No provider, storage, decoder or other external I/O; no opened/committed transaction.

For each ordered proof image, reload the exact workspace/media row with for_update
and populate_existing. Reconstruct the complete PlanningImageRowPinV1 from actual
creator, creation time, hash, size, MIME, dimensions and scope, preserving the
original image observed_at. Compare the existing shared row identity digest to
the exact proof commitment. Missing/foreign/changed metadata fails source_changed;
malformed proof is proof_unavailable. Preserve authorization exceptions and
unexpected database/callback failures. Empty images still receive every scope,
privacy, goal, transaction and time guard.

Return the exact immutable creative_local_witness(document) only after final
SQL guards. Its timestamp is the original document-basis commitment, not a newly
claimed byte inspection. This metadata port cannot detect out-of-band blob changes;
never claim current/permanent byte availability. Future generation uses actual
byte inspection, and media delivery must independently enforce private access.
Ordinary metadata loss makes current use stale; immutable history remains valid
unless semantic privacy erasure removes the retained plan graph.

Tests on both databases use genuine composed v5 documents from actual owned
reporting/image fixture ports where available: unchanged/empty/multiple witnesses;
creator/time/hash/MIME/dimension/scope changes; missing rows; session/membership/
goal/privacy changes; expiry during lock/guard and UTC folds; rollback/replaced/nested/
dirty root failures before autoflush; viewer allowed and unpaid read permitted;
no provider/storage calls or writes; original witness timestamps unchanged.
Combine with unchanged historical dependency checks demonstrating metadata loss
stales currentness but does not rewrite history. Whole Ruff/configured mypy required.
