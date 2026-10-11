# Google Reporting Catalog V1 — Frozen Offline Package Interface

Base6f47ce5. This is a separate v24 reporting catalog, not the v25 publication
WEBPAGE/PURCHASE custom-goal catalog. No public routes, storage, factory or live
capability is supplied. Queries reuse locally documented ConversionAction resource,
owner_customer, name, status, category, type fields; actual v24 provider compatibility
is unverified. MockHTTP does not qualify it. Required developer token remains.

Request: schema version, server-owned ReportingScopeV1 restricted to Google,
actor hex32, private original-session digest hex64, aware started_at, literal v24.
Caller proves all scope/session authority; DTO construction never proves ownership.
Context: exact request digest, expiry, excluded secret access/developer tokens and
optional excluded ten-digit login manager. Resolver and revalidator are injected.

Option: same-customer action resource <=128, owner ten digits, safe observed label
1–160, literal ENABLED, category/type 1–100. Each action emits two distinct options:
conversions and all_conversions, each exact selected_presence query-profile digest.
No default, type/category filtering or manager-owned action. Duplicate names allowed;
duplicate action rows reject. Option identifier hashes original actor/session,
exact scope/API and full option (including label/family/profile), excluding observation
time so fresh rediscovery can compare. It is not authorization or a bearer token.

Result: exact request digest, observed_at/expires_at, terminal pagination true,
action-page count1..100 and <=2000 options (1000 actions). Complete graph digest;
strict same-owner/profile/duplicate validation; canonical result <=256KiB. Lifetime
<=5min and context expiry. Account ID/currency/timezone verified on every acquisition.
A metadata mismatch or foreign-owner action fails the catalog rather than filtering
silently. Empty fully paginated catalog is allowed, never automatic selection.

HTTP: fixed Google v24 search endpoint, POST read queries only, no redirects/proxy
inheritance, identity encoding, connect5s/read12s; overall60s monotonic+aware clock.
Revalidate before/after every request and finalization; check time again AFTER
potentially blocking authorization. Check every response chunk and cap total bytes
at8MiB; cursor<=3000, <=100 action pages, <=1000 actions. Error bodies are neither
stored nor returned. No cross-call credential caching or logging; private HTTP flag
is restored. No claim of atomic provider snapshot across pagination.

Dependent work must implement actual original-session ownership/vault resolution,
fresh rediscovery confirmation+0091CAS, lifecycle/privacy and customer API separately.
