# Configured Optimization Customer API Freeze

The existing owned accounts and target-options endpoints remain; names and opaque
choices come only from the exact admitted native catalog. No customer qualification,
provider resource JSON or technical operating-policy knobs are accepted.

Under `/api/customer/v1/workspaces/{workspace_id}/execution/optimization`:

- `POST /budget-mandates`: `PrepareOptimizationMandateV1` contains meaningful
  `intent.selection` (current goal/revision, owned account, opaque option), confirmed
  total and named aggression. Optional mandate ID plus expected revision is an exact
  edit. Returns `PreparedOptimizationMandateV1` with exact period, currency, target,
  total and derived monetary caps, policy/preparation digests and state=draft.
- `POST /budget-mandates/{mandate_id}/consent`: `ConsentOptimizationMandateV1` binds
  current selection and exact revision/policy/preparation digests. Returns the same
  projection with state=active after original-session final authorization.
- Existing `POST /initial-reviews` and `/repeat-reviews` remain exact action intents:
  selected option, mandate ID/revision, budget amount or pause; repeat includes its
  original predecessor. Shared execution approval/run/recovery APIs remain unchanged.

Configured flow rejects technical `/mandates` create/edit and generic old consent
as bypasses. Legacy explicitly injected fixtures keep their existing API contracts;
legacy authority is not silently upgraded to configured authority. A new explicit
prepared revision can retain its existing ledger only when account/period/currency/
overall-cap and high-water invariants continue to hold. Native observation does not
supply admission or financial headroom. All runtime sources remain server-owned.

Source discovery releases the API transaction before native HTTP and reacquires the
original session, current goal and source generation afterwards. Preparation creates
the marked financial revision and exact sidecar in one transaction; failure at the
final fence rolls back both. Consent re-resolves native choice/current admission and
pinned operating policy before atomically committing exact approval. No assumed
hot-reload or cross-process policy revocation is introduced.

Generic marked revision reads validate strict stored origin and financial-policy
binding. Current forward optimization authority additionally validates the exact
configured policy/profile and requires marked provenance; runtime review, approval,
claim and final emission fences all retain their existing financial/current-source
checks. Historical reconciliation and settlement retain the original attempt/hold;
policy drift never authorizes a new request or releases an unresolved reservation.

This freezes contracts only. Required acceptance is the ordinary configured API
using actual private contexts and MockHTTP native inventory/admission/read/update/
readback, no getter overrides or seeded review/attempt/hold. Both databases, final
session revocation, scope/generation drift, legacy bypass, exact consent and unknown
no-replay must pass before claiming the configured journey works.
