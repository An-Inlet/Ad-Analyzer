# Owned Optimization Export

This isolated package starts from PR159 `c87a7ff30046f2c057984669143b9960804a721c`
and merges PR160 `3df38fcc162f69a491a9d7abb0d231836e49e5b1` (merge `cdc8942`).
Predecessor worktrees and branches remain unchanged.

Persisted existing-campaign optimization reviews, requests, responses, and receipts
now use their strict product schemas in customer archives. Reviews bind workspace,
account, connection, consent, plan/document digests and absent creation-source lineage;
requests bind workspace/run/attempt/step; receipts bind workspace/attempt/content digest.
Response shapes overlap across execution domains, so their persisted domain-separated
content digests select the schema explicitly instead of relying on union order.
Unknown shapes, extra provider bodies, altered lineage, and unknown response digests
remain unsupported omissions and make the archive incomplete.

Before the fix, all six actual optimization-to-archive scenarios failed archive
completeness: Google, Meta, and TikTok on SQLite and PostgreSQL. These scenarios run
actual persisted preparation, exact approval, claim, provider execution through mocked
HTTP, owned receipt creation, then bounded archive generation. They do not substitute
handwritten JSON for executed records. Negative archive-row tests cover scope,
account/connection/consent, run/attempt/step and content digest tampering.

Validation: 21 focused domain tests passed, including existing creation, activation,
settlement and outcome archive/privacy coverage. Ruff app/tests and configured mypy
(445 files) passed; git diff check passed. Logs:
`/tmp/inlet-export-optimization-before.log`,
`/tmp/inlet-export-optimization-final.log`,
`/tmp/inlet-export-optimization-mypy-final.log`.
An exploratory `mypy .` invocation failed duplicate-module discovery; the repository's
configured `mypy` invocation is the passing required check.

Full and hosted CI remain pending parent coordination. Export stays disabled by
default and retains the quiescent uniform-writer deployment gate. No live provider,
cloud, deployment, billing, retention, or advertising changes were performed.
