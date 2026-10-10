# Mandate API Scope Tests Use Current Drafts

The two remaining test_mandates failures occur in the setup's obsolete simulation
approval. The test itself verifies current CSRF, owner/workspace isolation, reads,
owner/admin pause and analyst/viewer denial. None requires an approved simulation.
Keep every original request/assertion and role iteration current. Use genuine current
created draft mandates in both workspaces, not historical execution authority.

Add an explicit keyword-only approve=True to the shared offline seed, preserving
all existing callers/default behavior. Only these two API cases pass approve=False;
only skip the obsolete approve call. Current create/flush/commit remain real. Assert
both revisions remain unapproved and draft, counters zero and no actions before and
after requests. Do not bypass any service guard or modify production code. Preserve
all other tests and shared seed statements modulo this conditional. This is a fixture
repair; it makes no historical/execution or live qualification claim.

Qualify current API both databases, bounded default write boundaries, and existing
seed users' retained simulation tests to establish default compatibility. Preserve
original API assertion suffix AST; whole Ruff/bare mypy/diff before code commit.
