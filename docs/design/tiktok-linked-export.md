# Linked TikTok Configuration Export

The existing owned social-configuration review table accepts a third explicit
schema discriminator for `LinkedPushConfigurationDocumentV1`. Export retains the
exact document version and digest and binds workspace, account, integration,
draft and source revision to the containing row. Unknown versions, extra data,
changed rights or foreign identity/row bindings are excluded as an unsupported
structured field; they do not fall back to untyped JSON.

The new strict nested observations contain aware timestamps and tuple fields.
Persisted records are JSON, so this schema is decoded with `validate_json` after
the existing bounded-JSON check. An initial positive regression reproduced five
Python-mode validation errors from JSON timestamps/arrays (1failed15passed).
The correction uses JSON semantics only for this new discriminator. Legacy v1/v2
schemas, validation paths and bytes remain unchanged; strict booleans and exact
rights commitments are not relaxed.

Validation:16 focused linked-document/export cases passed1.34s. Existing actual
owned Meta/TikTok configuration storage/approval and v1/v2 export compatibility
passed5 cases across SQLite/PostgreSQL in12.89s. Whole Ruff, mypy872, final scoped
mypy2 and diff checks passed. No database migration, live action or source
qualification was added. Coordinator and actual linked customer composition are
separate integration work; this export increment alone does not enable execution.
