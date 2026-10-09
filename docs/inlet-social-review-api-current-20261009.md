# Current Social Configuration API — Four Original Cases

Approved interfacea4253e7; implementation branches from integrated root8acd74e.
Tests only, no production, child producer, configuration4 or producer18 behavior change.

Closed retained consumer api reconstructs the actual original social source through
unchanged loader. Expected current document comes from real current selection with
API contract-test-v1 wording; legacyV1 expected document derives its original schema
and digest without upgrade. Final exact row check permits only these two reviews and
two approvals plus bounded actual-login effects. All source/financial/provider/schema
rows remain exact; provider attempts/responses/receipts remain absent, native_posts0.
The optional typed source.api_evidence is None for previous callers; no generic callback
or table exclusion is exposed.

Local replica fixture binds clients to source.engine (the actual owned SQLite file or
isolated PostgreSQL schema). Only this FakeProvider instance takes original mock issuer
and contact email. Ordinary login finds existing actor without rewriting identity; Bob
with same email remains a genuinely foreign user. Single-use login binding validates
exact new Bob row, two real sessions with cookie/CSRF bindings and ordinary TTL, and
known two exchange receipts with wall-clock-bounded expiry. All other graph rows exact.
Final expectation permits only Alice's actual logout revocation; Bob and other fields
unchanged. Unbound expectation permits no new rows.

All original API assertions and decorators remain AST-identical except removed
user-exists/issuer-subject-rewrite setup (replaced by stricter identity checks). Runtime
missing503, options, CSRF403, bad-answer422, creation201/nonexecutable, foreign403,
confirmation/replay, wrong-digest409, explicit legacyV1 seed/read/hash preservation/
requires-new-review/confirmation409, actual logout204 and subsequent401 all remain.
Existing runtime/media dependency injection is disclosed; no capability/guard bypass.

Each actual case additionally validates adversarial copies (not DB mutations): unbound
expectation, duplicate session/review/approval, changed retained issuer and workspace
must reject. These six checks per case are supplemental assertions, not new pytest
nodes or extra original-failure credit.

## Exact Evidence

`/workspace/inlet-evidence/20261009/social-review-api4/` retains raw logs/XML and owned
basetemps. Disposable localhost PG inlet_oct07_next_integration_ci with
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true; per-test schemas, no aggregate DB/reset.

- Initial SQLite gate:2 setup errors,2.332s. Ruff removed a renamed fixture import as
  unused, so replicas was unavailable before any API calls. Raw gate.log/xml retained.
  Fixed explicit fixture alias assignment; no behavior/expectation adjustment.
- Corrected SQLite Meta/TikTok gate:2 passed,25.919s, no skips/failures.
- Final selected4 plus bounded compatibility:24 passed,162.047s,
  zero skips/failures; exact selected4 present, remaining20 overlap compatibility.
- Initial type errors (strict union inference and pytest fixture __wrapped__ typing)
  preserved in mypy-initial.log. Added exact document union and explicit typed fixture
  return cast; no schema/authority changes. Whole Ruff/bare mypy1230/diff pass.

Commands use /workspace/inlet-venv/bin/pytest with exact paths below:

```text
-q tests/test_customer_social_review_api.py -k sqlite --basetemp=<evidence>/gate-artifacts --junitxml=<evidence>/gate.xml
-q tests/test_customer_social_review_api.py -k sqlite --basetemp=<evidence>/gate-corrected-artifacts --junitxml=<evidence>/gate-corrected.xml
-q tests/test_customer_social_review_api.py tests/test_social_configuration_review.py::test_exact_configuration_confirmation tests/test_social_customer_producer.py::test_produce_canonical_owned_plan_with_exact_cover_review tests/test_advertising_capabilities.py tests/test_planning_customer_boundary.py --basetemp=<evidence>/qualified-artifacts --junitxml=<evidence>/qualified.xml
```

Static uses whole ruff check ., bare mypy with /tmp/inlet-social-review-api-mypy and
git diff --check. Original identity mapping/assertion proof retained. Compatibility
overlaps already closed cases; only exact four passing originals can add recovery.
No live publication, new erasure coverage, quality-completion or Full rerun claim.
