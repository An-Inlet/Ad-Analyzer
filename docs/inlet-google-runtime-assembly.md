# Owned Google Execution Assembly

The ordinary customer execution API now has a request-scoped assembly path using
its actual database bind and original authenticated session. It constructs actual
Google OAuth refresh, named catalog, configuration qualifier, creation and activation
HTTP adapters. Legacy explicit runtime injection remains compatible. No source is
registered by default; absent configuration/source remains unavailable.

The separately pinned `GoogleExecutionManifestV1` is selected by
`AD_ANALYZER_GOOGLE_EXECUTION_MANIFEST_PATH` and
`AD_ANALYZER_GOOGLE_EXECUTION_MANIFEST_DIGEST`. It contains no credentials or
financial facts. Every configured lifetime/flag is required. A trusted Python
`RegisteredGoogleEvidenceSource` must match ID, profile digest and environment;
its factory result descriptor is checked before constructing contexts/transports.
Live manifests reject contract-scenario sources before IO. The shipped real transport
also rejects every contract-test manifest before constructing HTTPTransport. Offline
scenarios require an explicit MockTransport factory; registering synthetic financial
evidence alone cannot route it into real provider mutations. A qualified-live-source
label does not prove any bound: the existing financial readers and coordinator
validate complete facts, current mandate and accounting independently.

The current registry function deliberately returns None. Offline integration tests
install explicit server-only contract-test scenario readers, retaining the actual
PortfolioExposureReader accounting logic, and inject provider HTTP transports.
There is no request/body/settings mechanism to submit proof JSON or executable code.
Installing a manifest does not enable live operation without an actual approved
source implementation and the existing separate authority/qualification gates.

Owned credentials come from the actual current Google connection vault. Each
request binds the original session/actor, scope and generation around OAuth using
short private sessions. Tokens stay ephemeral; context and underlying transports
close on success and errors. No global principal or global database engine is used.
The Google bundle rejects direct social API execution before resolving evidence
sources, and its reader/context boundaries independently reject non-Google plans.
The shared inert social transport slots are not capabilities or enabled integrations.

Actual configured PostgreSQL testing exposed an existing activation read-phase
lock issue: identical receipt reconciliation returned the existing receipt without
committing, then the external qualification callback's private session waited on
that same workspace lock. Captured backend7331 waited on7325; holder's last query
was the receipt lookup. The exact local test process was stopped and its waiting
query canceled. `activation_review.prepare_activation` now explicitly commits the
completed reconciliation read phase before external qualification. The final
current/parent_graph/freshness rechecks remain unchanged. No receipt/financial
semantics were broadened.

The regression holds fixture time constant so identical receipts really take the
no-op path. It verifies no duplicate receipt or provider write, a single retained
parent hold, and original DB-session revocation during post-release qualification
preventing activation review. Unknown creation retains its original attempt/hold
and a subsequent advance only reconciles, without replaying the mutation.

Current acceptance is actual configured API on SQLite/PostgreSQL with approved
creative as input and no seeded execution reviews/attempts/holds/receipts. APIs
create and consent the mandate, discover/qualify configuration, review/approve,
claim and create the paused graph, then separately approve activation. OAuth and
provider requests use actual serializers through MockHTTP. This is not live
financial or provider verification. TLS browser integration is a dependent package.

Manifest cache is per process path/digest. Coherent policy rollout/draining old
processes is a deployment prerequisite; no distributed hot reload/revocation is
claimed. Meta/TikTok production assembly, qualified existing-campaign catalog and
optimization/replacement, settlement evidence and automatic-session worker assembly
remain tracked full-MVP work in the next-package proposal.
