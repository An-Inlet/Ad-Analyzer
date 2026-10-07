# V2 Execution Proof Storage

0081 follows0080. This package adds storage/export validation only; no v2 customer
handoff, automatic authority, financial qualification or live runtime is installed.

`initial_preview_execution_proofs` has composite primary key(review_id,workspace_id),
digest and strict hash-only document. Composite owned FK references a new unique
index on the existing link and cascades when that link is deleted. Adding an index
avoids rebuilding a populated SQLite parent with protected RESTRICT children.
Proof UPDATE always fails. Downgrade checks nonempty proof storage before any DDL,
then removes only the new empty child/index/functions. Prior reviews remain intact.

Portable SQL insert guards require a nonretracted owned link, owned v2 preview and
protected parent origin. They bind scalar/document IDs, preview/qualified-state/plan/
environment commitments, link review digest to parent, separate consent on one ledger,
and the existing planning/execution policy and intent references. SQL does not pretend
to compute canonical SHA fingerprints: ORM preinsert validation additionally verifies
strict documents and their digests, canonical original native observation and preview,
parsed financial review/plan/full execution binding, and reconstructed handoff intent.
Raw SQL writers remain subject to relational guards; malformed canonical content is
rejected by the strict bounded exporter, and must never be treated as authority.

V2 explicitly interprets link.intent_digest as the NEW handoff request digest and
link.mandate_digest as the separately consented EXECUTION policy digest. The proof
separately binds planning policy to PreviewRow.mandate_digest and planning ID/revision
to its typed PreviewIntentV2. V1 link meanings and bytes remain unchanged. The preview
is immutable; strict schema dispatch is mandatory before interpreting link commitments.
No additional version column is needed: the existing v1 guard rejects a v2 preview;
missing preview/link or v2 proof must deny, never fall through to manual/v1 authority.

The child is classified as protected workspace-scoped hash-only history, with a strict
16KiB document bound and no original-session export. It may remain as audit history
when preview deletion retracts the nullable link pointer. A NULL pointer cannot accept
a new/restored proof; link deletion cascades its proof. The protected parent origin
survives either erasure and blocks creation of a different review for that origin.
Proof export is historical, never a current eligibility statement. Future bridge
retry must return conflict on missing proof rather than recreate erased provenance.

Tests exercise both ORM metadata and actual0081 downgrade/upgrade with populated prior
review/link data on disposable SQLite/PostgreSQL, owned mismatches, immutable updates,
validly rehashed but contradictory parent bindings, canonical ORM validation, cascade,
NULL-pointer denial, nonempty downgrade refusal and malformed export. The positive
storage fixture builds internally typed preview and financial documents against owned
parents; it deliberately does not claim a customer-created v2 authorization journey or
qualified financial evidence. The future service must still validate original session,
current source/profile/goal, real consents, caps and period, and every forward financial
gate. Historical receipt/reconciliation/settlement paths are untouched.
