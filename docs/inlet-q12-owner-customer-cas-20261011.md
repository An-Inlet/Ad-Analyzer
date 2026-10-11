# Q12 Private V6 Customer CAS — Source Preparation

Source-only additive package initially based on `ce25c17`, now based on reviewed
diagnostics candidate `d99b0ea02e23766074dcdf5e1daa52e5d92ef605`. This base is
NOT fully qualified: diagnostics01 has 29 passed, 1 failed PostgreSQL fact-age
case and 2 sales cases unrun. These new Q12 cases will not qualify the entire
diagnostics candidate or retry its prior failure.
New `tests/test_owner_review_customer_cas.py` uses unchanged original-session V6
acquisition/upload/catalog/discovery helpers and primitive customer input bodies.
No production code, schema, helper, default policy or privacy behavior changes.

Exactly two proposed cases: the existing SQLite/PostgreSQL customer-engine
fixture. SQLite exercises sequential stale-request parity. PostgreSQL starts two
independent authenticated HTTP clients at a bounded barrier before the unchanged
service revise method's refresh/locks. No sleeps or mocked persistence/CAS.

The winner's exact replay is idempotent; changed content under that key conflicts.
Scoped graph snapshots cover heads, revisions, versions, dependencies, events,
request receipts, input/catalog receipt links and referenced catalog selections.
Immutable V1 rows exclude mutable heads. V2 retains the complete owner/creative
basis; obsolete V1 and forged current action decisions use current sequence1 and
exact separate refusal reasons. Six named financial helper models must remain
zero; no broader unqueried mandate/consent/obligation claim. Synthetic customer
and hashed scoped graph artifacts avoid cookies/provider bodies.

Planned IDs:

- `tests/test_owner_review_customer_cas.py::test_actual_v6_customer_edit_cas_replay_and_obsolete_decisions[sqlite]`
- `tests/test_owner_review_customer_cas.py::test_actual_v6_customer_edit_cas_replay_and_obsolete_decisions[postgres]`

Status: implementation draft; no pytest bodies or collection executed. Source
review, qualified-base update, static checks and exact runner authorization are
pending. Existing repository races and legacy HTTP cohorts will not be repeated.
No browser/human/usefulness, reconnect, provider-write or full-Q12 claim.


Candidate preparation: whole Ruff passed. Initial mypy rejected `table.name` on
SQLAlchemy's FromClause type; replaced it with the model's exact `__tablename__`
label. Original failure log preserved. Whole Ruff and configured no-path mypy
then passed (1,492 files). Collection-only selected exactly the two named cases;
no test bodies run. Evidence folder:
`/workspace/inlet-evidence/20261011/q12-owner-cas/`.


## Candidate-Only Execution Result

Authorized runner02 passed exactly two disjoint cases: SQLite1 passed35.56s
(original exit0/process38.200s); PostgreSQL1 passed46.91s
(original exit0/process49.040s). No skips/failures/errors. PG began only after
SQLite's exact XML pass and fresh per-node checks; source/head/diff checks also
passed after each process. Runner exited0. Run01 was prepared but never executed.

Manifest02 SHA256
`25a3e4d0fca7279061bba36db73a3c632162e444fd6e686819bed8491254f8e8`
and runner02 SHA256
`92828d6e12beae1ce261f53dd19efd038db8fdd4ac97598b896b57ea4f2ef9a8`
are bound by `authorization-02.json`. Per-case XML, original exit summaries and
synthetic customer/graph evidence are in the evidence folder above. Source hash
`61929e920e50deff46a579e73ec8c3c6c8af7c39df27b291ed129aaf806a698a`
remained unchanged from final static/source review through both cases.

This qualifies the stated actual V6 customer API composition on candidate
`d99b0ea` only. It does not close the prior diagnostics PG fact-age failure or
qualify the complete candidate. SQLite is sequential parity; only PostgreSQL
qualifies the overlapping admitted-request CAS. No repeated old cohorts, remote
writes, advertising effects or broader financial-table claims.
