# Planning Comparison Display

Display-only `renderPlanComparison` binds exact expected predecessor/successor versions
and digests, shows field paths and literal before/after values, distinguishes missing
from null, and prominently reports omitted changes. It states that decisions do not carry
over and document changes do not establish provider change attribution or business causality.
All values use textContent; rejection clears previous display. No API, session, decision
or export control is implemented by this component.

11 comparison/Chromium DOM checks passed in 3.41s. Real DOM coverage includes malicious-
looking changed text, no injected elements, omitted count disclosure, wrong-version
rejection and clearing. Ruff, prescribed mypy and node syntax/diff checks passed.
Authenticated selection/session/expiry lifecycle remains future controller work.
