# Actual Requested-Window Browser Qualification

Branch `codex/inlet-window-browser` consumes frozen service `f681f1a` and real
import fixture `ee889ec`. The application default remains V2 in this package;
the actual customer service is explicitly configured with canonical V3.

The authenticated HTTPS/Chromium journey uses actual customer routes, native Meta
mock reads, the 0090 56-day import, enabled offline billing, native target catalog
and receipt acquisition,
owned window collection, genuine composition, final checks and persisted versions.
The form submits seven-day primary and preceding comparison periods. Visible output
shows primary 100 clicks, 10 selected conversions and USD100 separately from the
comparison's observed zero. Distinct evidence references retain the exact requested
periods; positive conversions do not produce a spend-without-conversions statement.

A second real import removes selected-conversion observations across the source.
The prior version becomes source-changed, regeneration withdraws the positive count
without inventing observed zero, and the browser can still read the unchanged first
version and its identical exported artifact. SQL assertions show two saved versions,
no customer decision events and no provider execution attempts. No ready-made plan
or evidence bundle substitutes for the application pipeline.

Checks on both SQLite and PostgreSQL: `python -m pytest -q
tests/test_planning_documents_browser.py -k windows` with JUnit output: **2 passed,
0 failed, 0 skipped, 43.176 seconds**. Other journeys were intentionally deselected.
Evidence: `/workspace/inlet-evidence/20261008/window-browser/explicit.log` and
`explicit.xml`. Whole Ruff, bare mypy (1,111 files), Node syntax and diff checks passed.
An initial Ruff finding was a 102-character test line, corrected by wrapping only;
there was no failed browser attempt or product change in this package.

This is offline browser qualification, not default activation, a full-suite result,
live provider verification or a commercial release. Default activation is the next
bounded W1 step under `design/planning-window-default-activation-v1.md`.

Independent review closed `44307cb` without P1/P2 findings. The reviewer clarified
that this journey acquires a catalog receipt but leaves the target choices at their
default, so it does not prove saved-target receipt reuse. That separate acceptance
is covered by the existing target journeys and requested-window API tests.
