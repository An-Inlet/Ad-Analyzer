# Prepared Generation Pure Checks

Proposed contract for independent security review before implementation. Supersedes
raw-row witness replacement as the initial repair candidate. No SQL read or source
reconstruction is removed. Performance remains unproven.

## Boundary

For exact configured v6 only, prepare the deterministic generation entry, actual
bindings, owner bindings and selected/paired ticket assertions after composition
and before the final identity refresh. This goes beyond the measured 0.818694-second
entry/binding reorder: it addresses repeated pure selected/paired reconstruction
inside both selected-current checks around the creative recheck. It does not assume
that this work is sufficient; focused work counts and actual configured qualification
must establish that.

The preparation stores bounded immutable resident snapshots, not live models, SQL
rows, sessions, secrets or authorization facts. Use the existing callback-free
`version_row_admission._Snapshot` scalar/schema copier as a value copier only; do
not reuse its row admission or session permits. Each root is independently bounded.
Exact declared model classes, fields, private/extra slots and immutable scalar types
are required; unknown, shared/cyclic, oversized or custom graphs use the unchanged
path. Capture settings/provenance are included through complete declared fields.

Snapshot all inputs before validation. Invoke the original pure functions once;
compare snapshots afterward and of returned canonical copies. Any normalization,
unsupported value or mismatch cannot create a preparation. Keep original public
helpers and direct repository callers unchanged. Invalid/unpreparable values retain
the original validation/error path; do not turn preparation failure into acceptance.
Expected ValueError/HTTPException refusals discard preparation and defer to the
original save path after final authorization. Unexpected exceptions propagate;
there is no blanket exception suppression.

## Exact Prepared Operations

| Original Operation | Exact Operands Sealed | Remaining Work |
| --- | --- | --- |
| repository generation entry | ticket, complete creative bundle, candidate; returned ticket/candidate and capability | Original-session lock and all repository reads |
| actual bindings | validated ticket, complete bundle, validated candidate | All fresh head/input/parent/goal/account/privacy checks |
| owner bindings | same operands and capability | Original owner receipt read/recheck |
| paired ticket validation | ticket and reporting paired bundle, including canonical return values | All traffic reads and current graph comparisons |
| selected ticket validation | ticket and selected sub-bundle, including canonical return values | Saved catalog, reporting proof, selected graph, commerce reads |
| selected end assert_ticket | ticket and selected sub-bundle | Existing final authorization, entitlement and clock checks |
| paired end assert_ticket | ticket and reporting paired bundle | Existing post-media second pass, authorization and expiry checks |

Match complete current resident snapshots at each omitted operation. A successfully
prepared value whose inputs later change refuses generation; it must not silently
switch to a different prepared graph. Subclasses/custom timezones or unrecognized
values that were ineligible at preparation use the literal original path throughout.
No omission is authorized by ordinary model equality, JSON alone, a digest alone,
or an `isinstance` check.

## Invocation And Concurrency

The preparation is private and explicit, passed from the service to one repository
save and its two selected rechecks. Bind it once to the active SQL session, root
transaction and connection transaction. Reject nested, reused, closed, foreign or
dirty contexts and poison it on transaction/flush changes before publication. Do
not retain it in a module global, ContextVar, database or cross-request cache. Close
it on every return/error. A scope marker must remain invalid even if a callback
swallows an attempted nested use or forbidden flush.
Preexisting listeners on any collection the scope would modify select the original
path, avoiding installation/removal during an active dispatch. Track partial installs,
attempt all removals, preserve an active original exception and surface cleanup-only
failures. At publication, change only the pre-publication flush-rejection flag;
transaction/connection/reuse poisoning remains active through final snapshot checks.

Pure checked values have no freshness authority. Preserve every original SQL read,
row membership check, lock, source reconstruction and dynamic predicate, including:

- Original actor/session and identity checks, revocation/expiry and five-second age.
- Workspace/membership, connections/integrations/accounts, private source rotation,
  source generations and privacy revision.
- Entitlement, goal, input/version heads, original owner/catalog receipts and replay.
- Complete selected facts, capture/selection/current heads, completion/manifest,
  campaign maps, range receipts/jobs and presence sidecars, including absences.
- Commerce/goal progress and all creative/media currentness checks.

Both selected-current passes remain on their existing sides of creative callbacks.
Prepared snapshot checks also run before pre-CAS and after the final flush to bind
the exact candidate and evidence throughout publication. Storage serialization stays
at its original point, with mandatory validation; bytes/digests do not change. CAS,
pre-CAS/post-flush expiry, receipts, dependency rows and transaction rollback remain.
No provider IO while final SQL locks are held and no refresh within save.

## Required Evidence

Before production wiring, freeze a cause-specific regression showing the original
repeated pure operations in the two media-bracketing source passes. On final code,
assert successful preparation and exactly one original evaluation of each prepared
pure operation, unchanged fresh SQL/current-source call counts, and byte-identical
document/export/storage results. Measure final configured save/authority timing
without claiming helper-inclusive time as additive savings.

Test nested and direct frozen-model mutation, different ticket/candidate/policy,
custom/subclass/timezone fallback, normalization, preparation reuse/foreign
transaction, swallowed flush/nested errors, rollback and concurrent head/source
changes. Run source/session/ownership/consent/privacy mutations during refresh and
on both sides of creative rechecks on SQLite and PostgreSQL. Preserve real-time
pre-CAS/post-flush and existing six-second delay refusals. Qualify exact configured
v6 cases and required v3/v5 regressions on final source; do not overwrite failures,
duplicate the entire suite or award diagnostic acceptance credit.
