# Current Scoped Media Reader Regression Qualification

Base `ba68199`. The scoped media reader case previously called a fixture that
approved a simulation mandate even though its behavior needs only a workspace,
actor, actual uploaded PNG and local scoped media reader. It now creates that
ordinary Workspace directly, following the already qualified current campaign
media storage setup. Shared historical journey setup remains unchanged.

Original successful byte read, foreign workspace rejection and changed validation
digest rejection remain. The function explicitly runs under planning boundaries.
Both database variants plus 86 current execution/provider boundary cases passed:
**88 tests, zero skips/errors/failures, 7.613 seconds**. Whole Ruff, bare mypy
(1162 source files) and diff check passed. Evidence:
`/workspace/inlet-evidence/20261009/scoped-media2/{qualified.log,qualified.xml,ruff.log,mypy.log}`.
Two original failing identities are new; the other 86 overlap existing evidence.
No production behavior, public claims, provider calls or aggregate run changed.
