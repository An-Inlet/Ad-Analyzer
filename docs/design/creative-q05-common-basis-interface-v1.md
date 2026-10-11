# Actual private V5 three-platform Common Basis: proposed test interface

Design only; implementation awaits review. This is a new Q05 deterministic/artifact
subset, not equivalence to9d7aa2, full Q05 quality approval, browser qualification,
human expert assessment, or permission to publish advertising.

## Shared fixture

New `tests/creative_q05_fixture.py`:

`prepare_creative_q05_basis(engine, config, replicas, patch, artifacts) -> CreativeQ05Basis`

Frozen test result fields:
- `creative: CreativeCommonBasis` (existing exact Google selected positive10 basis,
  real uploaded128×128PNG/hash, private store, same owner/workspace/goal).
- `account_ids: tuple[int,int,int]` in Google/Meta/TikTok order, distinct and all
  owned by that workspace; no native identifier accepted as authority.
- `selectors: tuple[dict[str,object], ...]` exactly three real target-catalog-v2
  response selectors, one campaign per owned account; used only as normal API input.
- `body: dict[str,Any]` normal create input with exact two scenario intents.
- `native_calls: list[tuple[str,str]]` local read-only mock method/provider labels;
  no credential/request-header storage.

Use `prepare_creative_common_basis(...platform='google_ads',selected_value='10')`
once. Never concatenate three independently prepared bases: that would create
separate workspaces/goals/sessions and false common provenance. Add only owned
Meta/TikTok account+integration+encrypted-vault bootstrap rows to this same basis;
no plan, proof, performance or financial records are seeded.

Preserve the exact approved Common Basis: New York September primary/August
comparison, November goal12000/baseline8000/ceiling1000USD, reusable mug25USD,
original synthetic PNG bytes/hash, one available image/no video, creative capacity1,
restrictions and unasserted features. Original authenticated cookie must stay equal
through source reads, real upload, catalogue receipt acquisition, save/generate/
replay/read/export; compare privately without printing it. Existing goal revision
is reused, not rewritten to make scenarios pass.

## Native composition without authority replacement

Reuse the actual existing Google wire callback already installed by the Google
basis and actual MetaServer/TikTokServer response contracts. Build a single explicit
host dispatcher; obtain Google fallback before installing it. All calls are local
MockTransport. Google search POST is read-only; Meta/TikTok catalogue calls are GET.
Unknown host/path fails. Preserve actual vault/context/original-session readers.

`social_account()` currently resets BOTH social encryption keys each invocation and
installs a single-provider diagnostic_transport. Calling it twice unchanged would
invalidate the first grant or replace Google dispatch. Therefore the new fixture
must initialize stable synthetic social keys once, create both grants with those
same keys, and install one three-provider dispatcher. Prefer a narrow optional
pure wire/source-bootstrap extraction from social_common_basis_fixture only if
its provider-alone default path/bytes remain unchanged and preservation tests run.
Otherwise keep an explicit small test-only two-account factory in the new file.
No production resolver/getter override or fabricated returned catalogue is allowed.

Meta has two campaigns with observed child adsets and explicitly unavailable
selected reporting; TikTok has the ordinary campaign/adgroup catalogue, unsupported
selected mapping and no video. Use actual endpoint-returned names/owned hierarchy.
Choose the designated first Meta campaign by fixture native identity verified in
owned response, not arbitrary response ordering. All accounts USD/New York.

Acquire real `/planning/target-catalog-v2` receipts for all three campaign selectors
with exact primary window under the original session, after source/bootstrap work
is complete. Require full owned account/context joins. Google selected_reporting
contains only its genuine capture selector; social accounts must remain absent,
not receive copied Google counts or fabricated empty successful reports.

## Two separate customer alternatives

The normal create request has all three account IDs and these exact intents:
- option_a: Google400, Meta300, TikTok200, reserve100USD.
- option_b: Google300, Meta400, TikTok200, reserve100USD.

All amounts use integer micros. Each independently totals1000USD and keeps
customer-supplied provenance. They are never summed into2000 or described as native
budget settings/forecast/authority. Preserve actual historical100Googleclicks/
USD100/10selected events and comparison truezero separately from these allocations.
Social reporting gaps stay explicit; never sum platform events as unique customers
or attributed Shopify sales. Global creative capacity remains1 across platforms;
no promise of a new asset for every platform, and no hidden capacity override.

## Actual tests/artifacts

New `tests/test_creative_q05_common_basis.py`, parametrized by existing customer_engine:
1. Assert exact fixture inputs/source ownership and baseline values; retain actual
   upload bytes/hash, goal revision, selected capture and returned receipt bindings.
2. POST inputs through actual API, POST generate with canonical private V5 service,
   GET current/version/export and exact request replay. No constructed positive plan.
3. Assert each alternative's exact target/micros/reserve/total/provenance; distinguish
   selected observations from planned money/native settings. Assert explicit social
   gaps, observed child locations, complete private creative witness, production
   required/not_assessed, capacity≤1, no inferred visual/rights/features.
4. Execution/run/attempt/approval/reservation counts stay zero. First generation may
   perform approved read-only native acquisition; replay/read/export perform none.
5. Save new per-database canonical document+export JSON and SHA/provenance manifest
   under distinct Q05 packet paths. Never overwrite original v3/v4/provider-alone
   artifacts. No expert pass or broad frozen-quality completion from schema/tests.

Initial bounded matrix is one positive fixture/API case on each database plus
relevant default-fixture preservation checks. Existing legacy alternatives test
retains its own negative arithmetic cases; Q07 strengthening is separate unless
explicitly assigned. SQLite first, PostgreSQL only after coordinated slot release.
No tests or implementation were run for this design.
