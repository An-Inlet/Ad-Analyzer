# Reported Efficiency Preview Customer Consumer

This package connects owned completed Meta campaign reporting to explicit-objective
comparison and a persisted initial preview. `/app/initial-planning` uses real
customer APIs and the original revocable session. It creates no prior action,
measured treatment effect, execution approval, reservation, or provider mutation.
The existing manual optimization journey remains unchanged.

The customer chooses a named local campaign and confirmed goal, captures the
current completed report, enters a maximum reported cost per selected event, and
explicitly confirms that objective. The API constructs the cohort from the owned
stored observation; the browser cannot submit a reporting document or provenance.
The page displays every configured rule's parameters and the server-selected rule,
then shows chronological training/holdout counts, direction changes, insufficiency,
and explicit lack of empirical or causal qualification. No best-backtest rule is
silently selected. Configuration is absent by default, with truthful unavailable
status and no supplied numerical or aggressiveness defaults.

An optional current-budget read reuses the actual native target catalog. It is
independent of financial-runtime enablement but still requires an explicitly
configured server catalog. Only a campaign-level native budget owner matching the
reported campaign, account, currency, timezone, and environment can be selected.
A campaign pool must retain the complete native target topology. An ad-set budget
cannot inherit a campaign aggregate's reported efficiency. Native HTTP runs outside
any database transaction; original identity/session, source generation, current
report completion, goal, comparison inputs, and current policy are re-read afterward.

The exact nominal before/after amount additionally requires a matching separately
consented spending plan, exact period and target-set binding. Currency precision,
positive amounts, fixed limits, and explicit positive-change/aggressiveness bounds
are checked without rounding or silently clamping the selected step. The preview
always discloses that provider acceptance/minimum budget and remaining financial
exposure, action-count/cooldown capacity are unverified. A nominal budget is not a
lifetime spend estimate. Missing native context yields absent amounts, rendered
“Unavailable,” never zero.

Every delivery uses the fresh database-aware clock. Preview lifetime is bounded
by original session expiry, calibration/observation retention, native catalog
freshness, mandate end, and the configured preview lifetime. Reads revalidate
owned reporting and current goal/configuration; expired or deleted evidence cannot
be delivered as a current preview. Derived preview storage is technically bounded
under the workspace lock, including unswept expired rows. Source/privacy erasure
and calibration dependency deletion invalidate derived previews without touching
financial history.

Routes under `/api/customer/v1/workspaces/{workspace_id}/initial-planning`:

- `GET /options`: typed owned campaign names and explicit server configuration.
- `POST /captures`: local account/campaign IDs only.
- `POST /calibrations`: owned observation ID, goal revision, explicit CPA objective.
- `GET /calibrations/{id}`: current owned comparison.
- `POST /native-options`: current owned comparison/observation IDs; bounded named
  native choices and matching consented plans, with no provider identifiers.
- `POST /previews`: owned comparison/observation IDs and optional complete native
  selection. Objective/provenance come from the database.
- `GET /previews/{id}`: current owned preview, no authority or refresh of expiry.

All writes require original-session CSRF protection; responses are no-store. The
page clears results after objective/goal/account/workspace edits, session changes,
permission failures, or logout, and discards late responses. It never automatically
replays a failed request and never displays raw JSON.

Review handoff is **explicitly unavailable**. Future action handoff still needs a
separate durable source-retraction guard through every forward execution boundary;
this package does not impersonate the existing mature-candidate guard. Native
financial qualification, calibrated production policy, causal learning, and live
pilot qualification remain unimplemented/unverified where previously documented.

Tests use real HTTPS browser/session/CSRF routes, actual MetaSyncService completion
publication and concrete capture/calibration persistence, plus real
MetaOptimizationTransport reads over MockTransport. Shopify goal confirmation uses
its actual ledger/preview/confirm services. Explicit contract-test parameters are
not production calibration. No live provider call, Full run, push, or PR is part
of this local-only delivery.
