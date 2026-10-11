# R02 Fresh-Read Query Multiplicity: Source-Only Investigation

Based on the exact probe application `0b6fd79`; result ledger632ed82.
No test, provider call, instrumentation execution or optimization in this package.
Measured aggregate: initial generation8628SQL, save3146SQL, save wall3.042459s,
max final identity age3.042576s. Counts below are source structure, not measured
attribution of those totals. R02's original expiry cause remains unknown.

## Concrete Call Graph

`repository.save_generation` first reads the immutable current input and optional
parent version, checks exact candidate/bundle policy/proofs/refs/targets, then paid,
goal, account and privacy. Its `service.generate.final_sources` callback performs
fresh selected/image checks and original input receipt revalidation. After that,
`capture_retained_sources` takes another current witness before final authority,
CAS/row writes/flush and final authority again. The independent stages are deliberate
late-change detection and cannot be collapsed just because their outputs agree.

`selected_plan_local.capture_selected_proof` iterates every selected input account,
including social accounts without selected captures. Each
`selected_plan_retained.capture_selected_reporting_pin` calls its inner `proof()`
twice with guards and private grant/source comparison around them. Each proof
reads `_reporting`, selection head, and, for a selected account, the selected+traffic
pass. Thus one high-level three-account proof is six inner account proofs, not
one Google read. Social accounts still require current ownership/source evidence.

`selected_plan_witnesses.capture_selected_reporting_sources` itself calls
`current_proof()` twice. Each loops all accounts through the same double-proof
routine. For three accounts this is twelve inner account proof evaluations in
that witness operation, independent of earlier source checks. Do not confuse this
structural multiplicity with an exact SQL count: missing completions, account
platform, current receipts, selected capture and traffic presence change branches.

Inside each `_reporting` (`retained_sources.py`), current scope, campaigns, source,
completion and read_current are checked, then manifest and qualified presence are
read. Selected storage `_aggregate` independently checks `current_scope`, calls
`read_current` with a callback that checks that scope again, then loads exact
completion metadata. `current_scope` acquires workspace/account locks, refreshes
workspace, checks integration and provider connection, and verifies privacy and
native metadata. These paths explain repeated ownership/source query families;
none is currently counted separately by the observer.

The selected+traffic private pass already shares its selected graph within one
invocation under `_proof_pass_guard`. That guard rejects flush/reentry/transaction
replacement and is not a cross-pass cache. Do not reintroduce the earlier duplicate
load or extend its lifetime across the second proof.

Important negative finding: `selected_storage.historical_capture` already batches
all facts and campaign ownership rows. It uses a bounded fact query and a distinct
campaign query, then validates each fact in memory. `service.manifest` also loads
all campaign/day metrics with a single bounded ordered query. Sixty-one dates do
**not** imply sixty-one read ownership queries in these paths. The per-fact
`db.get(Campaign)` in `store_selected_capture` is an acquisition write path, outside
the observed final generation save; optimizing it would not address this interval.

Original input/catalog receipts are another potential source family:
`repository.inputs` validates historical owner receipt links only when
`google_daily_budget_intents` is non-null. Q09 probe04 has None, so that conditional
historical validation is NOT executed work in this probe and must not be attributed
to its query count. The later saved-receipt check does reload owned original
receipts with session/TTL/source/selection commitment checks. Historical and
current receipt purposes remain distinct, not interchangeable authorization.

## Smallest Reviewable Next Measurement Contract

The helper census is DEFERRED. The exact-one probe authorization is exhausted;
no further diagnostic execution is authorized or scheduled. Before changing
production, a separately approved evidence-only helper census could inspect the
same save interval, not another broad timing retry. Fixed allowlisted wrappers
could count calls and SQL deltas for `_reporting`, `current_scope`, `_aggregate`,
`historical_capture`, `manifest`, `read_presence`, and original saved-receipt load.
Report an explicit call tree or exclusive deltas so nested reads are not counted
as independent savings. No SQL text, parameters, row identifiers or argument
serialization. Counters bounded, original function called once, exceptions and
clock unchanged, cleanup reliable. Root must approve exact source and execution
separately. Current aggregate evidence is insufficient to assign3146SQL to any one
helper or conclude that a proposed change materially reduces latency.

## Candidate Optimization Boundary (Not Authorized Yet)

Only after that census, select one repeated *same-invocation* immutable graph load
or ownership-row family. Prefer bounded distinct-ID batching over lifetime caching.
The internal pass must privately own exact account/source/privacy/generation and
transaction/connection identity; caller cannot supply a trusted graph. Keep all
original-session authorization callbacks, lock ordering, final time/expiry checks,
raw copied-model validation, manifest/canonical commitments and full ownership
checks. Record invalidation on flush, reentry and transaction changes even if an
injected exception is swallowed; always detach listeners. Return immutable data,
never a reusable authority token or session-wide cached proof.

No reuse across the selected/image/selected boundary, the two account proof calls,
initial versus retained witness check, final flush or separate request is proposed.
A simple identity-map hit does not prove currentness under READ COMMITTED; replacing
populate_existing reads with cached ORM objects would change correctness. Likewise,
removing a workspace reread after a lock acquisition can hide changes injected by
SQL events; any batching design needs explicit before/after invariants, not an
assumption that 'the same transaction' means a fixed snapshot.

Required eventual regression contract: exact v4/v5 documents/proof bytes and
failure statuses; measured SQL counts on the targeted family; raw SQL changes to
source, privacy, selected head/facts, aggregate/traffic and campaign ownership
between fresh passes; same-pass mutation/flush/reentry rejection; missing/corrupt
sidecar fails rather than becoming a gap; full expiry and real >5second authority
delay still fail. Keep original failed R02 evidence and report performance without
claiming causality. No fresh-pass removal, deadline renewal or automatic retry.
