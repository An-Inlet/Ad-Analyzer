# Provider connection data-effect explanations

Child of `a5188c0`, following the reviewed provider-copy findings. Copy-only
production changes in `index.html`, `portal.mjs` and the Meta, TikTok and CRM
callback HTML. Google and the public site are untouched. No new controls,
checkboxes, requests, authorization, backend behavior or privacy policy.

The existing disconnect reviews, acknowledgments and result messages now disclose
workspace-wide saved-plan, recorded-decision and selected-reporting-evidence
erasure, including plans for other connected accounts. Retained imported reporting
and goals remain distinguished from erased derived plans. Running ads are unchanged.

Provider-specific boundaries are preserved:

- Meta reconsent warns when the account is already saved in this workspace, covering
  a stored `reconnect_required` row without implying every historically connected
  account still exists after disconnect deletes its connection row.
- TikTok and shared CRM callbacks warn conditionally for previously connected
  accounts; those source rows survive local disconnect.
- Shopify preauthorization explains that verified first binding as well as rebind
  invalidates workspace-derived plans. Its disconnect explanation still explicitly
  deletes imported Shopify data and distinguishes retained goal history and
  unavailable imported baselines. It does not promise raw reporting retention.

Existing browser journeys received bounded assertions for the actual callback,
review, acknowledgment and result text. Shopify consent checks the notice before
authorization and the existing disconnect review; the existing customer API browser
driver checks the actual Shopify disconnect result. No new test functions or
lifecycle fixtures were added.

## Qualification

Exactly 14 existing browser nodes, each once in a fresh process: seven SQLite then
seven PostgreSQL. Per database: Meta, TikTok, three CRM providers (Klaviyo/HubSpot/
Omnisend), Shopify consent, and the customer API journey. All 14 passed with no
failure, error or skip. No retry or observer/profiler. Case-time sum is 75.010s;
this is neither wall time nor a performance claim.

Reviewed immutable manifest SHA256:
`c18e6ea5bc46cc666f4ca3a499e8bfabf86818a5b59e21ef02e1f4f3b6f7577d`.
Runner: `01218fbbb750fafc1e9bf5a5ed9f275baf68392798cb5c52ac12f21620877238`.
Separate root authorization binds that manifest. Each next node required original
exit 0, exact unskipped XML identity, unchanged source/diff, resource floors, sole
pytest ownership and fresh output/basetemp/cache paths. PostgreSQL used the existing
explicit disposable local database and per-test schemas, without reset.

Whole Ruff, configured no-path mypy (1,487 source files), Node syntax checks for
production and modified test JavaScript, and whitespace checks passed. Mypy waited
for the other lane's slot release. Test source did not change after these checks.

Evidence root: `/workspace/inlet-evidence/20261011/provider-connection-copy`.
`manifest.json` lists exact commands and node order. `summary.json` retains all
source/evidence hashes, original results and XML identities; SHA256
`0012d5ea13b76852caebb97c44f70473a6227aaa235223304765d4535f18173a`.
Original preparation draft, collection, static logs, authorization, resource
snapshots and all 14 log/XML/result records are preserved.

This package qualifies explanation/control compatibility. It does not demonstrate
accepted-plan reconnect erasure for every provider or preserved-history reconnect.
The frozen Q11 history criterion and owner requirements question remain separate;
no retention behavior was weakened to satisfy them.
