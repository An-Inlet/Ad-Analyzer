# Capability-Gated Selected Planning Portal

The authenticated no-store capability endpoint reports the actual configured
canonical policy under current workspace access. It performs no advertising
provider or Vault initialization. The default remains v3: selected controls stay
hidden and legacy input JSON still omits selectors. Private v4 configuration exposes
optional, exact per-account Capture IDs. Blank choices serialize an explicit empty
selection, never observed zero. Saved IDs survive edits; removing an account requires
explicit clearing. Session changes and rerenders revoke stale controls.

The real TLS planning journey consumes a capture produced by actual 61-day range
and selected-capture API setup (provider transport is mocked). It signs into a new
session for the same owner, explicitly enters that retained ID, saves through the
public input route, recovers a lost committed response without another POST,
generates/persists v4, exports version 1, edits the exact retained selection and
generates version 2. Version 1 remains immutable. Switching back to v3 refuses an
edit that would drop selectors; replacing the session during capability fetch
clears the editor. Reporting-page automatic handoff is still absent and its honest
copy remains unchanged. This is not live provider or deployed product verification.

Checks:
- Final four actual TLS cases (selected and legacy, SQLite and PostgreSQL): all
  passed, no skips, 51.817 seconds (`final-browser-03.xml`).
- Four actual capability API cases: all passed in `api-browser-01.xml`.
- Three Chromium component cases: all passed, no skips, 6.722 seconds.
- Whole Ruff, configured mypy (1362 files), JavaScript syntax and diff checks passed.

Evidence: `/workspace/inlet-evidence/20261011/selected-planning-portal/`.
The initial combined run had five passes and one PostgreSQL fixture failure: a
cached helper retained a prior localhost origin, correctly rejected by CSRF. The
helper now imports before origin patching and explicitly uses each actual TLS
origin. Failed evidence, the bounded PG rerun and the final both-database regression
run are retained. Checks overlap and are not summed as unique coverage.

Predecessors: reviewed private consumer acf1c67 and retained dispatch 0e57b7e;
reviewed paired reader 4cd8fb1. No hosted runs, push, provider calls, ad writes,
merge, deployment or default-policy activation. Q01–Q16 and release gates remain
tracked separately. Next: actual generated-plan lifecycle archive and erasure.
