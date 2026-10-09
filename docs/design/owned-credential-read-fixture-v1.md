# Owned Credential Read Fixture

Scope: only `test_optimization_runtime_substrate::test_owned_credentials_context_and_cleanup`,
32 frozen failures (2 providers × 8 changes × 2 databases). Current body exercises
actual vault refresh, original owner session, source generation, billing, expiry,
lock release and context cleanup. It never invokes advertising mutations. Its
execution-heavy setup is obsolete for these assertions.

Private local setup reuses source-only catalog seed; actual owned account/integration,
Google or Meta source, actual session login. Google vault stores synthetic refresh
and uses original synthetic OAuth client config. Meta reseals original synthetic
access with NOW+2h lifetime. No manifests/execution runtime/mandates needed by the
body; its unchanged explicit optimization manifest remains. Real context manager,
authorizer, OAuth MockTransport, independent mutation transaction and every existing
predicate stay unchanged. Current foreign-provider, unknown/expired grant, billing,
revocation and post-IO expiry cases keep their parameters/IDs.

Only this function receives planning_boundary and explicit before/after zero-authority
fixture already used for TikTok reads. Other loader/no-network/vault tests unchanged.
No global shared fixture or production changes. The setup is local to this module,
not a shared interface or an implicit authorization for other consumers.

Qualification: preserve exact two SQLite baseline failures, run full module on both
DBs (32 repaired plus 9 existing pure cases), whole Ruff/bare mypy/diff. Independent
review before integration; retain all failed probes. No aggregate/provider calls.
