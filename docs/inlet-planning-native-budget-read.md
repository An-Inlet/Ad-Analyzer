# Owned Native Budget Read Checkpoint

This is local read assembly, not an enabled production runtime or financial
qualification. It follows the [frozen proposal](design/planning-reporting-runtime-contract.md).

Concrete callable ports:

- `load_planning_reporting_profile(path, expected_digest)` returns a frozen profile
  or `None` only when both arguments are absent; configured errors are sanitized.
- `MetaBudgetHTTP(context, policy, transport=..., clock=...).read(request, now)`
  collects the owned Meta account, campaign and complete bounded adset topology
  through fixed-origin GET requests. It has no mutation methods.
- `owned_meta_budget_reader(sessions, principal, provider, profile, configuration,
  clock=...)` is a context manager yielding that collector. Private sessions use
  the caller's engine and the original customer session, with real current goal,
  ownership/generation, paid-work/master-sync checks and encrypted Meta vault.
  Every HTTP boundary rechecks authority; no transaction spans provider IO.
- `parse_meta_budget(...)` is the shared neutral parser used by the existing
  qualified optimization adapter and the new collector. No qualification ID or
  financial period is added to read observations.

The initial collector supports USD with exponent2 explicitly. Other currencies
return `native_budget_currency_unsupported`; no two-decimal fallback or deployment
exponent override exists. This is a current implementation limitation, not a
restriction from the audit. Existing injected qualified optimization currency
coverage is unchanged. Daily and lifetime values retain distinct modes. Unsupported
flags or account/profile states do not become selectable options. Full topology,
strict cursor/page/target/response bounds, read deadlines, credential expiry and
observation lifetime are required. No external pagination URL is followed.

Root approved this bounded USD mapping. The primary Meta currency documentation
at https://developers.facebook.com/docs/marketing-api/currencies/ was not retrievable
in this session; the campaign reference returned429. No further retries or live
provider requests were made. This package does not claim live schema qualification.

Local evidence: the actual prior7767b54 adapter and refactored parser produced
byte-identical serialized Meta states for campaign and adset fixtures. Their exact
state digests are pinned in tests. Owned-vault tests use actual commerce refresh,
original customer sessions, current goal and native source records on both SQLite
and PostgreSQL; only HTTP transport is injected. Session revocation, generation
change and goal invalidation during the first response deny results before the
next HTTP request. Clients/transports close on success and rejection.

Still required: deployment settings/startup snapshot, ordinary API/worker assembly,
versioned v2 preview and strict lifecycle/export/feedback baseline dispatch. Existing
v1 preview and qualified handoff bytes remain untouched. No runtime factory is
activated by this collector checkpoint.
