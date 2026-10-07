# Activation, Settlement And Outcome Export

This delta extends the existing disabled-by-default, ephemeral customer export. It
adds no provider reads, persistent artifacts, deployment changes or spending authority.
The isolated branch starts from rootd2cf458 and incorporates reviewed settlement154
and root6eef6d8; predecessor export, closure and runtime branches remain unchanged.

## Explicit Supported Documents

- Execution review: discriminated creation-v1 or activation-v1 document. Activation
  binds its workspace/account/integration and plan/review digests to owned row fields.
- Attempt/response/receipt: existing creation contracts plus exact ActivationRequest,
  ActivationResponse and ActivationReceipt. Activation scope/run/step fields are
  checked against available owned scalar lineage; arbitrary raw JSON is never allowed.
- Settlement: exact `inlet.provider-settlement.v1` wrapper around typed
  SettlementSnapshot and SettlementObservation, retaining old ExposureEvidence
  compatibility. Checks distinguish no-committed-attempt from qualified-terminal
  evidence, bind reservation/ledger/workspace/environment/amount, recompute snapshot
  digest, and require internally matching original receipts and reporting proof.
  Exporting this historical evidence never executes settlement or authorizes spending.
- Owned assessment: `inlet.owned-outcome-assessment.v2`, bounded to256KiB before model
  parsing, bound to owned workspace/publication/generation/privacy epoch/receipt IDs,
  receipt sequence and digests, policy/input fields and assessment content digest.
  Its existing contract permits only insufficient assessment and no causal lift or
  spending authority. Export does not upgrade it into an optimization decision.

Unsupported schemas, extra fields, secret-like keys, invalid evidence or ownership
mismatches omit that JSON field and explicitly mark its section/archive incomplete.
The implementation does not silently convert missing customer domains into internal
exclusions. Existing intentional security/global/unclassified omissions remain reported;
completeness for supported customer data is not all stored data completeness.

## Actual Verification

Tests use the actual coordinator, mocked HTTP provider, persistent SQLite/PostgreSQL,
private media and archive builder. The journey creates the complete paused graph,
obtains separate activation approval, activates every reviewed target, cancels both
related local runs, records qualified contract-test settlement and exports the records.
A separate actual commerce publication and owned assessment is exported unchanged.
Neither journey contacts live providers.

Negative assertions reject foreign scalar ownership and injected raw JSON, invalid
assessment status/version/causal-lift claims and oversized assessment documents.
After the first real TAR chunk, an actual Shopify orders/delete privacy event deletes
the source-derived assessment and increments the shared export revision; the next
chunk fails closed and closes its ephemeral file. This is source-erasure fencing,
not an exception for an already-created archive.

The original serializers produced four archive-completeness failures on these actual
domains across both databases. Initial repaired execution/domain suite14passed.
Expanded archive/domain/privacy suite: **76 passed,1 SQLite-only row-lock skip**,
94.95s. Final exact-domain regressions after response/receipt digest binding:
**15 passed**,24.55s. Ruff app/tests, mypy434 source files and diff check passed.
Logs: `/tmp/inlet-export-owned-focused.log`,
`/tmp/inlet-export-owned-final-bound.log`, `/tmp/inlet-export-owned-last-mypy.log`.
No Full suite or live deployment was run by this package. The default export-off
runtime gate and quiescent uniform-writer upgrade requirement remain in force.
