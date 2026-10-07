# Linked Push Durable Service Checkpoint

The coordinator now discriminates linked Push plans and bound requests explicitly.
`CreationRuntime` gains optional `linked_tiktok`, `linked_context`, and
`linked_configuration_current` ports, all defaulting to None. Linked forward
creation admits contract_test only. A missing transport/context/current validator
blocks before emission. Existing Google and social v1 documents retain their
schemas and hashes.

`app.publication.tiktok_linked_review_service` provides server-only prepare,
checked, confirm and verify_plan operations against the existing owned
configuration tables. It parses persisted new documents in JSON mode, checks row
ownership/scalar commitments, and verifies the exact stored approval reference.
No endpoint accepts these documents as customer provider proof. The current
capability helper compares exact owned requests, identity and fresh permission
facts, not refreshed clock-dependent digests. BC publishing permission remains
unavailable in this helper; can_push and customer consent cannot supply it.

A dedicated test fixture builds the approved source, media, linked configuration
confirmation and separately consented financial review through real services. It
uses explicit synthetic qualification/exposure and mocked provider HTTP. It does
not seed execution records or bypass the obsolete-identity guard. SQLite and
PostgreSQL both complete all five disabled creation steps after a 30-second clock
advance with unchanged refreshed capabilities. Configuration JSON is actually
persisted and reloaded. Missing current validation blocks; removal of approval
blocks forward work while historical unknown reconciliation retains the original
hold and never repeats the mutation.

New CUSTOMIZED_USER creation on Inlet's TikTok-only placement is blocked at
prepare, approval, run admission, claim and final dispatch checks. Historical v1
parse/readback/reconciliation and existing-campaign optimization are preserved.
The dedicated legacy regression sets up explicitly historical records with the
new guard temporarily absent, then restores the real guard for every assertion.
There is no product or scenario exemption.

Checks actually run:

- Final linked durable/current-facts file: 4 passed across SQLite/PostgreSQL;
  slowest calls 7.62s PostgreSQL and 7.49s SQLite.
- Legacy forward/history file: 4 passed in the earlier combined cohort. The two
  newly added linked negative cases initially had a missing pytest import; after
  correction they passed, and the final four-case linked file passed again.
- Combined pure contracts/graph/HTTP/consent/export: 60 passed. Currency symbols
  are accepted while emoji/control and CJK weighted-length rejection remain.
- Whole repository Ruff, mypy on app plus five focused test/helper modules
  (513 source files), final scoped mypy (3 files), fresh-process import checks in
  both coordinator-first and transport-first orders, and diff checks passed.

Logs: `/tmp/inlet-linked-coordinator-currentfacts.log`,
`/tmp/inlet-linked-forward-history.log`,
`/tmp/inlet-linked-forward-history-fixed.log`,
`/tmp/inlet-linked-final-pure.log`, `/tmp/inlet-linked-final-mypy.log`.

## Remaining Assembly

This is **service acceptance, not configured customer API/TLS acceptance**.
The configured linked profile/catalog factory, customer configuration endpoints,
actual owned capability refresh binding and separate linked activation adapter
remain code work. Existing positive *future* legacy TikTok creation fixtures must
be migrated to the supported linked path; the guard intentionally makes the old
creation path unavailable. Do not describe this branch as a green assembled
candidate or enable it based on these focused checks. Root's immutable Full and
all remote/live/default activation gates remain unchanged.
