# Requested Window Reader And Evidence — Phase Two Proposal

Base `f2156f7`; documentation only, pending root review. The
[frozen pure contract](planning-requested-window-contract-v1.md) takes original V3
plus requested window. It validates a campaign subset, **not** ownership or the
whole completion graph. This proposal does not modify that interface, old report
DTOs, old policy outputs, imports, public comparison output, or UI.

## Explicit Policy Capability Mapping

Proposed new module `planning_documents/policy_capabilities.py`, a closed mapping
keyed by **both** policy version and generator version:

| Pair | Reporting mode | Local witness kind |
| --- | --- | --- |
| `inlet.descriptive-review.v1` / `inlet.descriptive-planning.v1` | `legacy_exact_window` | `local_reporting_v1` |
| `inlet.descriptive-review.v2` / `inlet.descriptive-planning.v2` | `presence_exact_window` | `local_reporting_v2` |
| `inlet.descriptive-review.v3` / `inlet.descriptive-planning.v3` | `presence_requested_window` | `local_reporting_v2` |

`reporting_capability(policy_version: str, generator_version: str) -> ReportingCapability`
returns a frozen private value with `mode` and `local_witness_kind` restricted to
this table. Unknown/mixed pairs fail; never fall back to legacy. Ticket/policy digest
checks still independently apply. The new version is not enabled by this proposal.
At retained-read sites the actual PlanVersion policy/generator fields select the
same table; do not infer a generator from an arbitrary policy string.

Replace exact `== QUALIFIED_POLICY` branches in adapter, final rechecker, ports,
composer, and retained-source capture with reviewed explicit dispatch. Preserve
all v1/v2 branches and their serialized bytes, fingerprint domains, fields, and
strict acceptance. New window documents are rejected under old policies. No
additional defaults are added to old serialized bundles or report DTOs.

## Owned Reader Boundary

Proposed `app/campaign_performance/window_reader.py`:

```python
class OwnedWindowReadContext:
    # Operation-local, bound to exactly one live Session transaction and account.
    # Private construction does not confer authority.
    ...

def prepare_owned_window_context(
    db: Session, *, principal: CustomerPrincipal, account: AccountRef,
    expected_source: SourceFence, expected_reporting_pin: ReportingPresencePin,
    authorize: Authorize,
) -> OwnedWindowReadContext: ...

def read_owned_requested_window(
    context: OwnedWindowReadContext, *, target: TargetRef,
    requested_window: ReportingWindow,
) -> RequestedWindowPerformanceV1 | KnownWindowGap: ...
```

Context contents are server-private: exact Session/transaction identity; account,
source fence and collection pin; current completion ID or proven absence; original
completion; one `PresenceReadContext`; bounded local/native campaign index;
validated originals indexed by campaign; DB-only authorization callback. Never
reuse across transactions, provider I/O, requests, or final-commit boundaries.
Returned reports are immutable values; context objects are never persisted.

Prepare under the existing deterministic owned account/source locks, after fresh
external identity validation outside SQL. Resolve current source/connection,
privacy, ordinary Meta provenance and current pointer. Recompute and compare the
existing whole-source reporting pin, including exact sidecar/current absence.
Use real current legacy/V3 readers, not DTO construction from presumed trusted
rows. A present completion with missing referenced rows/corrupt mapping remains
an abort, not `no_data`. Build the presence index once per context using the existing
transaction-bound `PresenceReadContext`; no whole fact graph validation per campaign
or per window. Cache each successfully read original campaign V3 only within that
locked context, then call the frozen pure projector once per requested window.
Existing legacy-reader authorization/manifest checks must remain; reducing their
SQL scans is not authorized by this proposal. The requirement here avoids repeated
whole **presence** graph parsing, not a claim of one total SQL query or benchmark.

Each read checks exact target account/connection/native identity against the owned
catalog target and local index; no name matching. Current DB-only authority remains
fresh before and after reads. A different transaction/completion/account rejects
context reuse. The final generation transaction builds a **new** context; no earlier
successful authorization or cached graph is carried into it.

## Private Window Evidence Shapes

Propose new private `window_evidence.py`, not additions to old EvidenceGap fields.
All models strict/frozen/extra-forbid/revalidate-copies; imported shared AccountRef,
TargetRef, ReportingWindow, EvidenceRef keep their existing contracts.

`WindowPerformanceEvidenceV1` fields:

- `reference: EvidenceRef` (`kind='reported_metrics'`);
- `target: TargetRef` (campaign only, exact catalog selection);
- `document: RequestedWindowPerformanceV1`;
- `measurement_scope='provider_reported_not_cross_platform_comparable'`;
- `attribution_qualification='unavailable'`;
- `completeness: Literal['reported_rows_only','unavailable']`;
- `conversion_qualification: Literal['reported_only','unavailable']`;
- `reasons: tuple[Key, ...]` (1–20 bounded entries).

`reference.document_digest` uses the existing planning fingerprint function with
new domain `requested-window-performance`, over the exact new DTO. Schema is its
new schema literal; reporting window equals `document.requested_window`. Original
manifest, generation, privacy, completion time, currency and provider/native
identity are bound through `document.original`. Reference expiry remains the actual
minimum native catalog deadline, never a new reporting TTL. Coverage is at most
`partial`/`unavailable` as existing evidence semantics require; per-metric coverage
lives in the requested summary. Selected qualification requires explicit original
event and a non-null selected-count summary, never default conversions or generic
counts. Selected zero still requires the pure projector's complete-day predicate.

Use a deterministic reference key `performance_window:<entry_digest>` (83
characters, within existing 96-character Key bound). `entry_digest` uses the
existing planning fingerprint function with domain `requested-reporting-entry`
and object fields `account_id`, `campaign_id` (the exact local campaign ID), and
`requested_window`. Normalize both aware window instants to UTC before its JSON
serialization, so equal instants with different offset encodings cannot produce
different keys. Do not alter the original input representation/digest or truncate
hashes. Account/native identity is separately checked in the evidence binding. Primary/comparison role is
inferred from exact input-window equality, not an independently trusted label.

`WindowReportingGapV1` fields:

- `account: AccountRef`;
- `target: TargetRef | None`;
- `requested_window: ReportingWindow`;
- `reason: WindowGapReason` (closed list below);
- `reporting_pin_digest: Digest` (exact matching per-account collection pin);
- `explanation: Text` (server-owned bounded copy, never proof).

`KnownWindowGap` is the reader's private return type with only `reason`; the adapter
binds account, exact target/window, explanation and pin. It cannot carry unchecked
caller-selected proof. Reader reasons are:

| Reason | Positively checked condition |
| --- | --- |
| `current_reporting_unavailable` | Owned connected source valid; actual current pointer absent. |
| `campaign_reporting_unavailable` | Current graph valid; exact catalog campaign has no local mapping. |
| `reporting_presence_unavailable` | Current legacy report and manifest valid; sidecar truly absent, not malformed. |
| `outside_imported_window` | Frozen projector's typed known incompatibility. |
| `unaligned_local_days` | Frozen projector's typed known incompatibility. |
| `requested_days_not_closed` | Frozen projector's typed known incompatibility. |

Adapter-only reasons `catalog_unavailable` and `no_catalog_campaigns` are allowed
only with `target=None`: respectively an already validated explicit catalog gap or
an actual owned catalog containing zero campaigns. These describe catalog coverage,
not proof that an account has no campaigns anywhere. Limited Meta/TikTok scopes stay
visible. All reader reasons require `target` (one per exact catalog campaign/window).
Missing selected cells or sparse calendar rows are valid reports with explicit
summary coverage, not a way to discard awkward data into a gap.

Catch **only** `WindowProjectionUnavailable` for its three known reasons after the
original V3 has passed real owned-read validation. A present corrupt sidecar,
invalid DTO, source drift, generic HTTP409, authorization/billing failure, capacity
violation, unknown timezone/invalid source metadata, or changed privacy aborts the
whole operation. No broad `ValueError` fallback. Google/TikTok without presence
produce explicit gaps under the new requested-window mode; retain their native
catalogs and existing legacy reporting endpoints. They do not become selected-event
qualified. No legacy full-window totals are relabeled as a requested subset.

## Exact Set And Bundle Contract

Propose `WindowEvidenceBundleV1` as a separate private bundle with existing fields
`operation_id`, `input_digest`, `privacy_revision`, `collected_at`, `catalogs`,
`commerce`, `context`, `reporting_pins`, plus:

- `performance: tuple[WindowPerformanceEvidenceV1, ...]`;
- `window_gaps: tuple[WindowReportingGapV1, ...]`;
- `gaps: tuple[EvidenceGap, ...]` restricted to existing **non-reporting** gaps.

Keep existing maximum-account/evidence counts and 32 MiB collection bound. Count
both successes and gaps toward the total window-evidence bound; refuse an overbound
campaign × window product before building partial output. A maximum-size two-window
request may therefore be unavailable; no silent truncation or increased bound.
An additive protocol return union can accept old EvidenceBundle or this new type;
v1/v2 consumers cannot accept the new branch.

`assert_ticket` preserves all existing source/context/commerce/freshness rules and
requires v3 policy, exact reporting-pin account set with no duplicate pins, and:

1. Define windows `W=(primary,)` or `(primary, comparison)`, enforcing existing
   ordered/disjoint comparison semantics. For each collected catalog, define `C`
   as all exact campaign targets, not only fixed allocations and not child targets.
2. Required slots are `(account, canonical_entity_key, window)` for every `C × W`.
   A successful entry or a target-bearing gap must occupy each slot **exactly once**.
   Reject both success+gap, duplicate, foreign, swapped selector, omitted campaign,
   unrequested window, or a gap's pin unequal to the account reporting pin.
3. For a catalog with zero campaign targets, require exactly one target-null
   `no_catalog_campaigns` gap per window; successful entries are forbidden. For an
   account with an explicit catalog gap and no catalog, require corresponding
   target-null `catalog_unavailable` gaps. Reject target-null substitutes for any
   actual campaign slots. The new branch additionally rejects conflicting catalog+catalog-gap evidence.
4. Each target exactly matches catalog kind/native ID/account/canonical/selection
   and catalog evidence key. No matching only display names or canonical keys while
   ignoring snapshot selection. Evidence keys are unique across both windows.
5. Validate all reference bindings and original/subset DTO invariants, collected-at
   and expiry boundaries. A valid primary does not erase an unavailable comparison.

## Final Recheck, Absence Pins, And Retained Reads

The v3 adapter captures the existing ReportingPresencePin for **every selected
account** before external reads, as v2 does. Its digest includes full current
source/mapping/completion/manifest state plus complete presence header/facts or
absence. A reporting-gap field points to this account pin; it does not invent a
manifest digest for missing data or persist client proof. Final transaction first
rechecks all account pins and owned catalog/source fences, then reconstructs all
successes and known gap predicates using new contexts. Require exact projection
fingerprints and the exact success/gap slot set. This catches absent→present,
mismatch→available, changed mapping, and changes outside either subset; never
validate only successful entries. Existing service final authority-age and expiry
checks run after all waits and before/after persistence.

Retained PlanVersion still stores immutable input windows and evidence references,
not the full transient bundle. Reuse `local_reporting_v2` unchanged for v3 through
the explicit policy table: currentness depends on the complete source witness,
including absence and mapping, rather than trying to reconstruct discarded gaps.
No window details are added to the old source digest formula. v2 witness bytes and
v1 legacy behavior remain identical; new policy identity distinguishes the meaning
of new evidence references. Viewer checks remain DB-only/read-role scoped; no
owner-only reader callback during history access. Corruption/legacy missing proofs
retain their current bounded stale/abort handling. No migration is proposed.

## Deferred Public Behavior And Acceptance

Do not enable a new public comparison renderer, fields, edit controls, rates,
deltas, or performance claims in this phase. Primary action assessment may consume
only exact primary-window evidence under v3 when that composer integration is
separately authorized. Comparison refs can be collected/validated without implying
that current action text interprets them. v1/v2 policy/generator output golden
fixtures and report DTO bytes must remain unchanged.

Before production integration: actual owned Meta import→reader→API tests on both
DBs for primary/comparison subsets, each known gap, no missing-calendar zero, full
source absence/replacement/corruption races, changed out-of-subset facts, exact set
omission/swap/duplicate, foreign scope/session/privacy/expiry denial, and final
rollback. Instrument presence graph validation/indexing to verify once per context
and reject reuse after transaction change; do not infer latency from counts. Keep
Google/TikTok gaps and all three native catalogs tested. Add goldens for old report,
plan and local witness digests. This proposal itself runs no tests or network and
closes no quality case.
