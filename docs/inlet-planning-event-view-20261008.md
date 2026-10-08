# Customer Decision And Report Display

The display-only `plan-events.mjs` renders one bounded, scoped immutable customer event
page. Decisions and customer reports are separate, with exact plan version/action,
recorded time, actor, digest and superseded event references. Retractions preserve the
original report in history. Reports explicitly remain unverified; the display never
infers provider state, a present application status or causality from an event chain.
Pagination and continuation are explicit. It accepts current customer decision/report
families only; a future observed-status controller requires separate support.

All customer text uses textContent, with no controls, links or network activity. A bad
or foreign response clears previous output before rejection. The future authenticated
controller owns session continuity, pagination requests and clearing on account changes.
No customer controller or authenticated journey is claimed by this component.

Actually run: real Chromium DOM test `tests/test_planning_document_view.py`, **1 passed
in 3.396s** (also preserves existing document/comparison checks). Covers literal hostile
text, separate application/retraction records, unverified provenance, page continuation,
foreign scope, authority flags, malformed chronology, duplicate sequence, invalid
retraction, and clearing. Whole Ruff and mypy **1045 files** passed; node syntax check
passed. Evidence: `/workspace/inlet-evidence/20261008/planning-event-view.{log,xml}`.
