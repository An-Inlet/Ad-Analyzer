# Owned Fixed-Window Meta Acquisition

The operational comparison worker reuses the actual Meta inventory, campaign-day
HTTP, staging, pagination and terminal publication path. Its `rf_campaigns`,
`rf_adsets` and `rf_insights` checkpoints distinguish a fixed report from the
ordinary rolling run even after runtime removal or job deletion. Existing optional
child-detail behavior is preserved. No provider mutation is introduced.

Each page takes workspace, selected original user/session/membership, then native
source locks. It pins the selected job identity: a rejected first job cannot cause
a second owner's request to be selected after the source lock. Terminal checks
revalidate the original authority, source generation, configuration receipt,
window, actual completion/manifest and fresh application/database time. Expiry
during HTTP rolls back the new publication and preserves the previous report.

Due rolling imports take priority. Fixed runs restore the prior rolling coverage
and cadence and retain actual acquisition start/completion separately. Repeated
reports require distinct actual completions and configured spacing for the same
window. Exact returned campaign days are retained; omitted days remain missing,
and explicit zero rows remain zero. A removed job or disabled runtime clears the
fixed staging and cannot resume it as a rolling import.

No numeric production profile is installed. The five-table0077 migration, lifecycle
classification and conservative retraction after every terminal account publication
are the companion package. In particular, complete correction/derived-feedback
acceptance requires that integration; this acquisition commit alone is not B17
completion or qualified learning.

## Verification

Actual original Meta optimization receipt and owned job admission → mocked Meta
wire pages → terminal retained capsules, on SQLite and PostgreSQL:
`pytest -o addopts='' -q tests/test_reported_feedback_acquisition.py`:
**16 passed in28.86s**, `/tmp/inlet-fixed-window-final.log`. Includes four distinct
acquisitions, spacing, rolling checkpoint preservation, missing versus explicit
zero, runtime/job/session/generation loss, two-owner selection and expiry during
terminal HTTP. Reports make no additional provider POSTs. Ruff and configured
mypy686 passed. Earlier two failed assertions expected a generic failure label;
the importer correctly returned its sanitized checkpoint error. Corrected tests
assert the actual error and unchanged data/IO behavior.

An earlier adjacent baseline run recorded61passed/3failed before companion
registry/historical-fixture integration, `/tmp/inlet-fixed-window-baseline.log`.
Those results are not an assembled pass: two failures were missing lifecycle
classification, one was a0076 historical dependency order later repaired on root.
The complete composed run remains required after0077 integration. No Full or remote
operation was performed by this acquisition slice; root separately runs frozen0076
Full. No live credentials, provider calls, deployment or customer spend occurred.
