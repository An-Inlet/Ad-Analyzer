# Q13 Writer Readiness And Customer Report Corrections

## Observation Writer Is Not Dependency-Ready

Source assessment at `ae030a34` confirms there is no qualified planning native-field
producer or production constructor for a supported `ProposedField`. The pure comparator
and reserved observation DTO/view do not supply field extraction semantics or provider
qualification. Raw status is not qualified as delivery status; effective landing-page
and inherited/effective country-target rules are absent. Current generated creative and
investigation actions cannot be turned into native edit proposals to fabricate evidence.

Defined the future ownership/provenance/idempotency/correction boundaries before any
writer implementation in the [admission contract](design/q13-observation-writer-admission-20261012.md).
That contract requires exact original session/paid owner/account/connection/privacy/action
binding, an admitted read-only native adapter, retained normalized proof, atomic event/
receipt/dependency append, fresh authorization on replay, and distinct observation
invalidation versus customer correction/retraction. Native semantics, proof retention and
observation invalidation/reader contracts remain prerequisites. No writer, observation
route, production fixture adapter or runtime activation was added.

## Independent Acceptance Gap Closed

Added a configured V7 customer-report correction lifecycle test. Existing repository
races and V6 serial reports did not cover this actual HTTP/configured-service/archive
join. This package changes tests and documentation only; it does not implement a new
customer service or native observation path.

The fixture creates and generates a real Meta V7 plan using parsed settings, real
planning service, configured media and SQL, with synthetic identity/provider transport.
The original report says the customer completed creative review; it does not claim an
implemented ad change. A supplied `verification: provider_verified` field is rejected
with 422 and no graph changes. Every retained event is a `ManualAssertion` with
`verification=customer_report_only`, bound to the original document/action digests.

Two independent clients retain the original session and correct the same report head.
On PostgreSQL, a barrier coordinates concurrent requests before service identity refresh
or transactions/locks; this proves concurrent-request CAS behavior, not overlap of
particular database locks. SQLite exercises sequential CAS parity explicitly. Both
outcomes are saved in finally before assertions, without replacing an active original
exception if artifact persistence fails. No sleeps, clock changes or retry-to-green.

On both databases exactly one correction returns 200; the other returns 409 with
`plan version or event sequence changed`. The losing request creates no receipt/event,
and immutable input/version/dependency/catalog rows stay unchanged. The scoped plan has
input/version heads 1/1 and event sequence 2, exactly two events and four request receipts.
The winning statement, reported time, original actor and superseded event are exact.

The same case verifies:

- Exact original/correction request replay and receipt lookup, including after later
  input revision and withdrawal; changed intent under the same key conflicts without
  changing the graph. A different key is not inherently invalid.
- A real input revision makes a new correction against the old inputs stale and refuses
  it without partial state. Historical withdrawal is still permitted and appends exactly
  sequence 3, linking the correction with null reported application time. This is stale
  input coverage, not a newly exercised provider-evidence expiry scenario.
- API history preserves original report, correction and withdrawal in order. Version 1
  export retains the original document/digest. A real customer workspace archive download
  contains those exact three assertion documents, not observation records.
- Foreign-customer reads/writes and revoked-session history/replay are refused without
  changing the scoped graph. Privacy erasure removes all six planning row categories;
  a fresh authenticated session cannot read or replay the erased results (404).
- Advertising provider call lists remain unchanged after generation, and six financial/
  execution table counts remain zero. No advertising write, implementation or lift is
  inferred from customer statements.

## Exact Verification

Final packet `/workspace/inlet-evidence/20261012/q13-customer-correction04`, manifest
SHA-256 `365d1c8776d676b5b25620330767cab1afe79480d12fa27702c9f5de41a556a5`,
predecessor `ae030a34` plus frozen source/diff, 1,886 source hashes.

All eight commands passed: whole Ruff, configured mypy (1,570 files), exact collection,
diff check and four runtime cases without skips. Two existing component cases protect
pure report/observation/export separation and actual Chromium mixed history/document
rendering. The new lifecycle case then passed SQLite, followed by PostgreSQL. Process-
duration sums: static 8.720s, component 9.414s, SQLite 13.192s, PostgreSQL 21.194s.
Original exits/logs/XML/exact node identities/resource samples/source-integrity checks
are retained. No interruption, kill escalation or surviving process member was recorded.
This is focused acceptance coverage, not full-suite, live provider or release evidence.

Four outcome/history files are copied durably under `retained-report-artifacts`, with
individual hashes and an index bound to the manifest. They include synthetic report
bodies and retained plan/archive documents; they are not privacy-filtered operational
diagnostic payloads. The new API/archive case is not a new full browser correction
journey; the separate existing Chromium component covers rendering only.

Earlier packets remain distinct:

- Attempt01: Ruff passed; mypy stopped on two inferred request-dictionary types. Remaining
  static checks and all runtime cases were unrun. Added explicit test dictionary types.
- Attempt02: four static and two component checks passed. SQLite stopped at archive
  creation because the test key was shorter than the existing 16-character minimum.
  Remaining archive/revocation/erasure assertions and PostgreSQL were unrun. Corrected
  the fixture key only; no archive behavior change or acceptance credit follows.
- Attempt03: Ruff stopped on the longer fixture-key line. Remaining checks were unrun;
  wrapped that call before attempt04.

Independent review covered contract/gap selection and source before execution; final
source/evidence/artifact and documentation review precede the local checkpoint.

## Remaining Work And Holds

Q13 still needs one qualified native-field extraction/proposal contract, durable proof
retention and observation invalidation semantics before a writing service can be built.
Do not accept an arbitrary injected snapshot as qualification or reuse customer reports
as provider facts. Full Q13 and multi-field partial comparison remain incomplete.

V6 and V7 remain default-off/selectable and release-unqualified; V3 remains default.
INLET-REL-20261012-01 remains open. These event-correction passes do not qualify
concurrent generation or explain the historical authority failure. Local branch
`codex/inlet-w1-followup`; no push, PR, hosted CI, merge, deployment, live provider/model/
payment call, credential operation, customer ad change or spending.
