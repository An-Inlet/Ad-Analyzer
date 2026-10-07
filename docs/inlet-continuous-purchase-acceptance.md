# Continuous Fresh Customer Purchase And Planning Acceptance

Local successor to `7bb02e9`, branch `codex/inlet-continuous-purchase-acceptance`.
The extended `tests/test_fresh_brand_pilot.py` uses the assembled application over
real localhost HTTPS and Chromium with SQLite/PostgreSQL. It begins with zero users
and workspaces; no customer, connection, goal, billing entitlement or consent rows
are seeded. The explicit nonproduction Stripe offer comes from the existing offer
fixture and does not choose commercial launch defaults.

## Continuous Flow And New Recovery Coverage

The actual visible journey signs in, provisions an owned workspace, requests test
checkout, handles a lost provider-accepted response, recovers the original purchase,
and reconciles a signed webhook through the real billing worker. Returning from the
provider before reconciliation cannot grant entitlement. Recovery preserves one
original checkout idempotency key.

Google OAuth and account selection use the ordinary UI twice, proving reconnect
preserves one owned connection. Shopify OAuth runs through the ordinary callback
and the actual import service consumes mocked HTTP, creating the measurement
ledger. The customer creates and edits a goal before preview/confirmation, gives
explicit planning-mandate consent, handles a stale consent revision, and separately
reviews a supplied campaign draft.

The existing second-identity flow cannot read the first brand's goal or campaign,
invoke its diagnostic provider IO, or inherit its billing state. It provisions its
own workspace through the API/UI; the original customer subsequently signs back in
and recovers the original goal, campaign and paid test entitlement.

Added actual goal-progress API/rendering and reload preserve the same saved
revision/digest. This fixture's November target has not started: numeric imported
sales remain null and spending authority false. This is honest monitoring of that
state, not evidence of sales achievement or mature action outcomes. Revoking the
original sessions in the database is an explicit adverse operator control; the next
customer refresh clears displayed progress, returns401 and performs no provider IO.

## Explicit Boundaries

Only provider HTTP/consent pages, identity SDK/verifier and deterministic worker
clock are fixture boundaries. The test invokes the actual commerce import and
billing reconciliation workers; it does not claim a deployed scheduler or live
provider/payment qualification. Local TLS material and test-only keys are generated
or supplied by existing fixtures and never represent external credentials.

The mandate here is **planning consent**; campaign approval is **Approved For
Offline Planning**. Provider execution/automatic admission tables remain empty and
the unconfigured optimization surface is asserted unavailable. The next concrete
bridge is the fresh owned customer and account→configured execution origin/financial
source→separate exact execution consent/review→worker/readback. Existing configured
execution suites exercise this separately using contract financial evidence. Their
passes cannot be relabeled as completion of this continuous purchase-to-execution
bridge or as production financial qualification.

No live purchase, provider action, hosted retry, deployment or Full run is part of
this package. No application change was needed for the new checks.

## Actual Validation

- Initial SQLite-only probe passed, `/tmp/inlet-continuous-fresh-sqlite.log`.
- `python -m pytest -ra tests/test_fresh_brand_pilot.py --durations=5`: **2 passed
  in19.54s**, no skips, SQLite and PostgreSQL isolated fixture schemas in the
  disposable `inlet_oct07_next_integration_ci` database. Log:
  `/tmp/inlet-continuous-fresh-both.log`. No frozen Full database was touched.
- Whole `ruff check .`, prescribed `mypy` (948 source files) and `git diff --check`
  passed. Mypy log: `/tmp/inlet-continuous-fresh-mypy.log`.
