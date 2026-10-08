# Planning Version Comparison Foundation

`compare_versions(previous, current)` accepts reparsed immutable PlanVersion values
only when workspace/plan identity, consecutive version and exact parent digest agree.
It reports field paths and before/after values. Actions, scenarios, briefs, evidence
and accounts use stable document keys, so list reordering cannot imply a changed
recommendation. Manual step order remains meaningful. Missing versus present null
is explicit. Version-header author/time stamps are excluded; evidence timestamps,
input revisions and policy/generator changes remain visible.

The deterministic comparison returns at most 500 changes with an explicit omitted
count. Consumers must display that count and retain access to the complete versions;
this is not a claim of exhaustive explanation for larger differences. Values are
untrusted customer/provider text and must be rendered with textContent or escaped
serialization. No decisions carry over, no source refresh is performed, and document
changes are not evidence of who changed provider settings or caused business outcomes.

Checks: 62 pure tests passed in 0.25s (10 comparison plus document contracts), Ruff,
prescribed mypy (1,031 source files) and diff check passed. Includes foreign/stale
predecessors, unsafe model copies, exact source/rationale changes, HTML-like literal
text, unchanged/reordered collections and explicit 600-change truncation.
No service/API/UI integration or live behavior qualification yet.
