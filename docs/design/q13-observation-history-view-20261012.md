# Q13 Observation History View Boundary

Consume the existing reserved ReadObservedStatus response variant as a distinct
read-only history item. Preserve strict page sequence, cursor, workspace/plan,
unique event IDs and no-authority guards. Validate every item before rendering any
of a mixed page. Decisions and reports retain their existing actor, recorded time,
supersession and customer-report-only semantics.

Observations must not invent actor, recorded_at or supersession fields. Validate
typed expected/observed values, missing reasons, unique proposal keys, derived
status, bounded limitations, native evidence/target account congruence and historical
observation intervals against event.observed_at. Do not compare to today's clock:
expired evidence can remain valid immutable history. Render values and URLs solely
as text, with no controls or clickable links. Label matching as supported-fields-only,
show unavailable reasons and provenance/intervals, and state that matching does not
establish implementation, actor, change time, delivery or business lift.
Preserve server microsecond ordering and reject impossible calendar dates. Validate
closed nested evidence shapes and the existing 400-day reporting-window ceiling.
Legacy missing-value comparisons may retain evidence under the existing DTO; show
that evidence without inventing an observed value. The new pure comparator emits
null evidence for missing values.

The payload lacks normalized facts and original plan bytes. Browser checks cannot
recompute their digests, independently verify original-action binding, authenticate
a provider or establish present ownership. Those remain server obligations before
an observation writer is introduced. No producer, writer, route, schema change or
provider qualification is part of this package. Partial is a reserved DTO status,
not a newly supported multi-field action or claimed positive end-to-end fixture.

Verify through actual Chromium DOM using comparator-produced synthetic observations
and separate customer report/retraction history. Cover matching/conflicting/missing,
exact URL/country rendering, historical expiry, malformed/cross-scope/source/time/
authority/union/status/page rejection and safe literal text. Retain existing document
and comparison assertions. This is a display fixture, not authenticated API/database
observation acceptance or completed Q13.
