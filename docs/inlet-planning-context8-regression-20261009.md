# Current Owned Planning Context Regression Qualification

Base `eaa0f8b`. Reuses the independently reviewed Google candidate source producer:
it calls the original durable ready fixture with unchanged defaults and preserves
the confirmed November 1 goal period. Current code reloads exact mandate revision,
policy digest and account; both API replicas use the yielded engine (including the
file-backed SQLite engine). No extra candidate work or original principal check is
performed after the original user issuer update.

All eight current ownership/context cases retain their original assertions,
parameters, clocks, real login/logout, wrong-owner and source/goal invalidation.
The separate DST/ambiguous-day test is unchanged. No retained execution override
is used; the current function is marked planning boundary.

Full module plus both current execution/provider boundary modules:
**95 passed, zero skips/failures/errors, 104.536 seconds**. Eight original failure
identities are newly covered; one existing DST case and 86 boundaries overlap.
Whole Ruff, bare mypy (1175 files), and diff checks passed. Initial mypy correctly
found newly inferred heterogeneous JSON payload types; an explicit test JSON dict
annotation fixed this without behavior changes. Both mypy results are retained.

Evidence: `/workspace/inlet-evidence/20261009/planning-context8/` contains log/XML,
static checks, and AST assertion-preservation proof (all original assertions plus
three exact source-binding assertions). No production code or aggregate run changed.
