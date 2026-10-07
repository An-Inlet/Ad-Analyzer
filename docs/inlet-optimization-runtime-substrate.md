# Optimization Runtime Substrate

This package supplies configuration and owned credentials for the existing-campaign
runtime; it does not register a customer getter, API, evidence producer or live source.
Existing Google/Meta publication configuration and policy bytes are unchanged.

`optimization_configuration.load_optimization_execution_configuration(manifest_path,
expected_manifest_digest, policy_path)` returns the strict manifest and operating
policy, or None only when all inputs are absent. Both files have 16 KiB bounds and
reject duplicate keys. Manifest digest pins the policy; environment and evidence
profile must also agree. Returned models are canonical copies: nested rules themselves
are frozen, primitive-only models in a tuple. No mutable policy containers survive.
Partial inputs, invalid fields, mismatched pins or profiles yield a fixed error code.

`optimization_contexts.owned_optimization_contexts(sessions, authorize, actor_id,
manifest, configuration: Settings, clock, transport)` yields a request-owned context
with `optimization(ExecutionAccount) -> OptimizationContext`. It takes ownership of
the explicitly supplied transport and closes it and its ephemeral cache on every
exit. Enclosing runtime code must not separately own/close that same resource.

Every request checks the selected provider before vault/DB/HTTP work, then original
session/actor, paid entitlement and current account/integration/native generation
under the canonical workspace lock. A private session closes before Google OAuth
refresh; another fresh owned snapshot follows. Cache entries are request-local and
bound to scope and exact encrypted grant. Meta uses the current grant's explicit
aware expiry; missing/naive/expired expiry is unavailable, never given a fabricated
lifetime. Both providers resample time after final authorization, so waiting cannot
return an already-expired context. No PublicationScope or mandate identity is forged.

Google Vault accepts an additive optional Settings argument; existing callers retain
the global default while this factory explicitly uses its supplied configuration.
Ciphertext format and encryption behavior are unchanged. Secrets are excluded from
OptimizationContext repr and serialization. No credential is persisted by this code.

`optimization_sources.registered_optimization_evidence` returns None. Existing pure
source admission remains responsible for exact descriptor matching before factories
run. `optimization_transport.optimization_execution_transport(manifest)` refuses
contract-test or disabled-live before constructing real HTTP; real transport retries
are zero and environment proxies disabled. Context injection is a trusted Python
composition seam, never browser-provided code or evidence. Tests use MockTransport.

Current context production does not supply qualification, exposure, replacement or
settlement facts. The configured runtime must admit a real source, retain original
session fences after all other IO and bind current provenance before using credentials.
No default live activation, autonomous work or spending permission is introduced.

Validation: the final substrate plus configured Google/Meta API and frozen contract
batch passed 78 tests in 120.28 seconds on SQLite and PostgreSQL (isolated disposable
schemas). It includes actual vaults, original sessions, OAuth MockHTTP, post-OAuth
revocation/source changes, denied billing, unknown/expired lifetimes, expiry during
final authorization, unsupported provider before IO, request cache reuse and exact
transport cleanup. Explicit non-global Google vault settings are tested independently.
Whole-repository Ruff passed; mypy over app and substrate tests passed 457 files;
git whitespace checks passed. No Full, hosted, live provider or deployment action.
