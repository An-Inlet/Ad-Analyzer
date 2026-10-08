# Native Target Catalog V2 Integration

Reviewed catalog `5535021` is integrated with qualified P01 and the V1 catalog on
`codex/inlet-planning-mvp`; frozen assembled code is `382895e`. Independent review
closed the exact entity/settings/key/owner correspondence, advertiser/source binding
and platform coverage findings before integration. No production write capability
or execution-only account catalog was restored.

The new versioned endpoint supplies owned native names and advertiser/entity/parent
references across Google, Meta and TikTok, including Google ad groups. Native
settings and metadata have separate coverage/read intervals and the earliest actual
expiry. Missing/over-bound names and social scope/ownership limitations stay explicit.
Old inventory serialization and digest domains are unchanged. These are read-side
building blocks, not a completed comprehensive plan or live-qualified integration.

Assembled checks with approved disposable PostgreSQL and SQLite:

`pytest -ra tests/test_planning_metadata_api.py
 tests/test_planning_metadata_contracts.py tests/test_planning_metadata_binding.py
 tests/test_planning_metadata_pagination.py tests/test_planning_target_catalog_api.py
 tests/test_advertising_capabilities.py tests/test_planning_provider_transport_boundary.py
 tests/test_planning_customer_boundary.py`

**283 passed, no skips, 201.22 seconds.** Includes final repaired contracts,
all-three-provider actual MockHTTP readers, legacy V1 API, current ownership and
session/source/expiry checks, and default transport/customer write denial. Whole
Ruff and prescribed mypy (**1011 files**) passed; diff checks passed. Raw evidence:
`/workspace/inlet-evidence/20261008/planning-catalog-v2-integrated.{log,xml}`.

Reviewed historical test partition `c7bc5e2` was also integrated: seven additional
explicit retained-engine modules, while operations attention runs under the restored
default planning policy. Its separate141-pass/2-expected-SQLite-skip and12-pass
evidence is recorded in `inlet-planning-test-partition-20261008.md`; do not sum
overlapping cohorts into a unique product acceptance count.

Next work is native-target customer display and reviewed comprehensive document
contracts, then owned persistence/version/decision/manual-application/export flow.
Sixteen synthetic quality cases were frozen before recommendation composition.
Schema review found event revalidation and typed fact-provenance gaps; repairs are
in progress before dependent persistence. Full-suite historical fixture adaptation
also remains. No aggregate Full, hosted CI, live provider call, remote push, main
merge, production migration or deployment occurred. Hosted diagnostic hold and
the Actions budget/stop policy remain unchanged.
