# Standalone Google Shared-Owner Types

Base `d8e5d6b`; branch `codex/inlet-google-budget-owner-types`. Approved standalone
slice only: new google_budget_intents.py, google_budget_owner_contracts.py and pure
tests. No existing input/context/action/API/service/composer/capability/storage
fields changed. No current plan behavior or default V3 change.

Exports: GoogleDailyBudgetIntentV1, ResolvedGoogleDailyBudgetIntentV1;
GoogleDailyBudgetOwnerWitnessV1; GoogleBudgetOwnerUnavailable;
derive_google_daily_budget_owner(catalog, owner_key);
owner_facts_digest(witness); resolve_google_daily_budget_intent(intent, witness).
The last helper performs pure exact value binding, not original-session ownership
or discovery-selector authentication. It rejects currency/account/evidence/facts
mismatch and requests above the observed native amount. Scenario/period-ceiling
constraints and original receipt resolution remain future consumer obligations.

Derivation requires complete native and metadata campaign coverage but allows
unavailable unrelated adgroup settings. It derives the full owner set before
REMOVED filtering, checks native/metadata status agreement, retained removed-row
settings, exact count and narrow ENABLED/STANDARD/DAILY/micros sharing profile.
The representative is deterministic. Full catalog commitment/strict copied values,
UTC cross-node windows and minimum expiry are revalidated; witness encoding is
bounded. Stable facts exclude acquisition envelopes while retaining source,
member identities/metadata/status/settings and policy; a fresh acquisition can
have a different full witness but equal facts. Unknown profile is typed unavailable;
malformed graph remains a validation failure.

Independent source review identified that legacy CatalogEvidence does not compare
reference.source_revision with account.connection_version. The new helper now
requires their equality without altering legacy validators. Factory/copied witness,
full digest and stable-facts regression paths cover this exact repair.

No hash is claimed to authenticate a provider read. No DAILY amount qualifies total
period spend. Positive native-setting requests remain hypotheses; no actionable
NativeBudget, write authority or runtime activation is added. Actual owned-session
receipt acquisition, consumer intent persistence, save/history joins and customer
UI remain separately reviewed work.

## Exact Checks And Failures

Durable evidence: `/workspace/inlet-evidence/20261011/google-budget-owner-contracts/`.

- pure-01: 1 failed, 0.388s. New synthetic reference used metadata start rather than
  the true minimum native/metadata observation start. Corrected fixture envelope.
- pure-02: 25 passed, 0 skipped, 2.735s.
- pure-03: 26 passed/1 failed, 2.498s. Test assumed legacy catalog accepts an
  ambiguous-fold expiry expressed in equivalent UTC; Python's legacy cross-zone
  equality conservatively rejects it. Kept legacy validators unchanged; tested
  accepted offset equivalence on unambiguous observation, and real fold expiry
  extension independently rejects in the new helper.
- pure-legacy-04: 104 passed, 0 skipped, 7.911s. Includes new tests, Q08 standalone
  extraction/import/nested serialization goldens and existing creative composition.
- pure-05: 1 failed, 0.400s. New strict generation join exposed the pure fixture's
  inherited stale source_revision. Set fixture reference to actual metadata version.
- pure-06: final 30 passed, 0 skipped, 2.445s, including generation-join regression.
- Whole Ruff passed; configured no-path mypy passed over 1,436 files. Format/diff
  checks passed before freeze. No legacy golden updated or production guard weakened.

All logs/XML retained with SHA-256 evidence manifest. No PostgreSQL/provider/live,
remote, hosted, deployment or upload work. Test slot released at terminal.
Preflight: workspace 1,709 MiB, scratch 4,635 MiB; cgroup headroom
17,179,869,184 - 14,729,101,312 = 2,450,767,872 bytes, above 512 MiB reserve.
