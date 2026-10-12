# Prechange Retained Document

Synthetic actual SQLite API generation/current/export/replay artifact from qualified
`0b9962a`, before typed provenance implementation. Full exported document, not rewritten
or stripped by the new implementation. No real customer/provider data.

Original artifact: `reporting-comparability-attempt01/sqlite-01-0-q09-api-artifacts.json`.
Original artifact SHA256: `6a542295d1a841c42d2ba44c7173495e8760394d7ceeade8ad529d4aa0b057f8`.
Document digest: `55e7570b06d6f25a86c3f8862f0281c73d1698a8b50d194b8ad58b1bac193280`.
Fixture file SHA256: `81f40580521e03caa8eccc95188b25c2929a7608610283ccfd5b55b25a1186e3`.

Interim enriched v1 fixture: original qualified a9c4bc3 SQLite export, preserved for
read-only compatibility. Document digest `a8b52c7cda6f3de5a812100238c36b2def9459f25610c5f4cea005f97ec49ae2`.
The two .py.txt sources are exact PlanVersion and selected pin definitions from
0b9962a, used in an isolated Python reader with unchanged transitive validation helpers.
This tests actual strict prior DTO readers, not a deployed old-image restoration.

Pre-settings fixtures (source548c351): `pre-settings-capture-v1.json` was serialized
from the existing pure graph fixture before production edits, not from a live/old
persisted row. `pre-settings-plan-v2.json` is the complete actual earlier SQLite
API-generated document from provenance-version-boundary-attempt03's first typed
artifact. Fixed byte/document digests are in test_capture_settings_contract.py.
Exact prior selected-contract and PlanVersion DTO sources are retained as
pre-settings-*.py.txt for old-reader refusal checks; this is not a full old-image
restore/rollback exercise. No fixture is rewritten to new versions on read.
