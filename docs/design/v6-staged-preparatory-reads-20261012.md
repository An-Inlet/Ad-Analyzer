# V6 Staged Preparatory Reads

## Scope And Existing Contract

The larger sequential matrix preflight returned 200 for its first workspace and
409 for its second before preparation. Recorded fact 20 expired at a lock guard
at 5.05 seconds; the lock wrapper itself took 2.539 ms. The ten pre-preparation
refreshes and source order attribute this to the collector's final joint context;
that attribution is a source-supported inference, not a recorded callsite stack.
This is separate from the earlier unexplained failure and from contention.

`OwnedCreativePairedReader.collect` retains the original one-transaction final
reporting → creative → reporting contract, including V5/V7 callers. The new private
`collect_for_generation` path accepts only canonical V6 with the original ticket and
session. Only the configured V6 generation service selects it. No request field,
settings switch, capability claim or customer-controlled authority bypass is added.

## Explicit Preparatory Contract

Collection already spans independently authorized read contexts and external media
reads. The V6 generation-only path splits its final three checks into three bounded
read contexts. Each context performs full provider revalidation BEFORE SQL, then
fresh canonical workspace/user/session/membership checks using the original identity,
issuer, subject, session digest and authenticated time. It checks the SAME fact after
the complete stage and closes its SQL session BEFORE the next provider refresh.
A fact expires after five seconds unchanged. There is no timestamp reset, renewal
under locks, retry, replacement principal or continuation after a refused stage.

Reporting stages retain exact goal/source/privacy checks, original retained catalog
and selected/traffic reconstruction, paid-work checks and original reference TTLs.
The media stage retains exact original image rows/proof, ownership, goal, paid and
privacy checks. No original ticket, receipt, source pin, observation or expiry is
restamped. Strict bundle/ticket and post-context reference-expiry checks remain.

The returned bundle is explicitly PROVISIONAL: released locks mean it no longer
claims simultaneous reporting/media currentness at collection return. This changes
only the V6 preparatory contract; it is not a transaction-equivalence claim. A media
change after its stage may be discovered at publication rather than collection.
Retained source values are evidence, never continuing authorization snapshots.

## Atomic Publication Remains Mandatory

`PlanningDocumentService._generate` still prepares deterministic evidence before a
separate full original-provider refresh and final SQL transaction. Publication keeps
canonical local authorization locks, current ownership, session revocation/expiry,
role, read-source connection eligibility and privacy checks; exact plan/input/version/goal,
source fences, retained receipt/capture/content and media comparisons; joint
reporting → media → reporting verification; original evidence deadlines; CAS;
version/dependency/request insertion and post-flush guards. It atomically rolls
back on rejection. No source-currentness conclusion from an earlier stage replaces
these reads, and no final authority fact is renewed. Owner spending authority and
approval requirements do not change.

A revocation or source change between stages must stop the next applicable stage or
final publication. Tests commit such changes between CLOSED contexts, not inside
locked transactions. Media changes after the media stage must fail before version
or generation-receipt publication. Unexpected exceptions retain their identity and
all contexts clean up. No V3/V5 behavior, deadline or promised campaign capacity is
reduced to make a test pass.

## Validation Gate

Read-only independent review must cover the exact diff and regressions before the
single changed-code larger preflight. Preserve all earlier manifests/results. Run
focused boundary regressions and static checks first, then the exact failed larger
SQLite node once with first-invocation evidence. Stop on any unexpected failure;
only successful preflight and the final independent manifest gate permit matrix
execution. Per-workspace inventory results are now persisted immediately so a later
failure cannot lose an earlier successful document-size observation.

The [verification checkpoint](v6-staged-reads-publication-blocked-20261012.md)
records the passing boundary/compatibility tests and single SQLite larger rerun,
followed by a separate PostgreSQL final-publication expiry. Matrix qualification
remains blocked. Planning authorization does not grant advertising execution consent.
