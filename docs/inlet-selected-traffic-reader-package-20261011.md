# Owned Traffic Reader And Historical Pin Validation

Branch `codex/inlet-owned-traffic-reader` starts at root `3b8181e`.
Interface freeze: `93fec36`, [exact SQL ports](design/selected-traffic-owned-reader-interface-v1.md).

## Implemented Ports

`app/planning_documents/selected_traffic_reader.py` supplies:

- `load_raw_range_traffic(db, *, account, expected_source, selected_pin)` returning
  `RawRangeTrafficGraphV1 | KnownTrafficGap`. It requires a clean caller-owned SQL
  transaction, recomputes the current local source fence, validates the exact
  selected capture/selection/aggregate and complete map, then resolves at most two
  receipt IDs for that exact owned completion. It never chooses latest.
  Presence corruption aborts even when a receipt is absent. Current success checks
  the complete retained traffic graph against the complete SQL manifest and exact
  selected aggregate/map. Missing provenance is a typed gap only after those prior
  selected validations; no current-map disagreement becomes a gap.
- `KnownTrafficGap` has exact account/selected-pin binding, a fixed explanation and
  the two reasons `range_traffic_provenance_unavailable` and
  `unsupported_traffic_profile`. An unrecognized present Google producer aborts.
  Pair-level `reporting_pin_digest` must use the complete retained account proof's
  `state_digest`, not the selected pin alone.
- `validate_historical_raw_range_traffic(db, *, expected_pin)` reconstructs the
  exact immutable receipt/header/facts by the retained request ID. It validates all
  digests, metadata, profile, aggregate and retained fact campaign ownership/native
  identities. It does not compare today's DailyMetric rows, current pointer, source
  grant, TTL, privacy counter or complete current campaign map. The original full
  campaign-map hash remains an opaque saved commitment, since that map is not stored
  alongside the pin. This port does not pretend to reconstruct it.

The additive `PreparedRawRangeTrafficProjection` in `selected_traffic.py` validates
and indexes a whole graph once, exposing readonly `pin`, `snapshot()` and
`read(campaign_id, requested_window)`. The existing standalone projector delegates
to it. Repeated projections never reparse the entire graph.

These ports perform no identity/provider I/O, commits or implicit authority refresh.
The caller still guards the original customer session before/after and retains
workspace-first lock discipline. No proof/history/bundle/runtime files were changed.

## Offline Evidence

Evidence directory: `/workspace/inlet-evidence/20261011/selected-traffic-reader/`.
Final combined reader/prepared-producer cohort: **40 passed, zero skips**,
81.501s on SQLite and PostgreSQL (`final.xml`/`final.log`). Whole repository
Ruff and configured mypy pass (1,349 sources); diff check is clean. No broad baseline.

Actual API fixtures perform raw61-day acquisition, customer event discovery and
confirmation, and selected HTTP capture before invoking the reader. Explicitly
synthetic native catalog data is used only by the existing legacy-import helper,
not as raw traffic or selected capture provenance.

Coverage includes full exact-current graph and September/August projections,
400 prepared projections without graph reparsing, actual legacy aggregate absence,
old receipt without a sidecar, stale selected-map rejection, raw fact loss, metric
changes, native campaign identity changes, duplicate completion receipts and privacy
changes. Historical pin validation survives a later real import and an additional
campaign; fact loss, identity changes, receipt deletion and semantic erasure reject it.

Failed fixture logs remain retained: the first selected ownership mock returned the
catalog's extra fields rather than the exact two-field query response. Another
absence test deleted a live receipt, which correctly advances privacy; the final
absence case instead uses an actual legacy import that never had a raw receipt.
Receipt deletion is now tested as current and historical denial, not absence.

## Remaining Boundaries

Root owns optional traffic proof pins and retained history wiring; the paired bundle
and composer remain a separate package. Nothing here registers a planning capability,
enables a live factory, grants advertising authority or claims Q01 is already closed.
MockHTTP establishes executable code behavior, not live provider qualification.
