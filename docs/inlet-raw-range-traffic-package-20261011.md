# Raw Range Traffic Producer And Pure Projection

Branch: `codex/inlet-raw-range-traffic`, based on reviewed interface commit
`162ec0e`. Scope is the first producer/DTO/projection slice of
[the approved traffic interface](design/selected-traffic-context-interface-v1.md).

## Implemented

- `app/campaign_performance/raw_range_traffic.py::store_raw_range_traffic`
  writes the existing immutable presence tables from the actual validated
  `GoogleAggregateRangeV1` acquisition, never inferred numeric SQL defaults.
  It verifies the acquisition/receipt binding and the entire supplied campaign
  mapping, including campaigns with no metric rows. Its producer profile is
  `google.v24.campaign-day.raw-required-traffic.v1`.
- `range_publication.acquire_range` invokes that helper inside its existing
  transaction before retained receipt/source/authority guards and commit.
  Receipt, metrics, completion, job and presence rows roll back together.
  Replay of an old receipt does not synthesize a sidecar.
- `app/planning_documents/selected_traffic_contracts.py` defines the dependency-light
  `SelectedTrafficPinV1`, explicitly reexported by `selected_traffic.py`.
  The latter defines the bounded immutable whole graph, summaries/window and
  `project_raw_range_traffic`. Full graph validation precedes slicing; the
  commitment includes the entire campaign map and immutable receipt/header/facts.
- Projections use exact closed local days and UTC instants. Actual omitted rows
  remain unavailable or partial. Only all explicitly returned days support a
  complete zero or total. Generic aggregate conversions are deliberately
  unsupported as selected conversions and never appear in traffic summaries.

The producer's inventory mapping is exactly its returned campaigns. A later owned
reader must supply the complete current owned map, including retained older
campaigns, and bind it to the selected capture. The pure DTO does not establish
SQL ownership, currentness, customer authority or live provider qualification.
The 32 MiB graph bound can reject fewer than the maximum 50,000 rows; never truncate.

## Verified Offline

Durable logs/XML are in `/workspace/inlet-evidence/20261011/raw-range-traffic/`.

- `combined.xml`: 53 passed, zero skips, 56.043s, actual SQLite/PostgreSQL raw
  MockHTTP publication plus existing range API regressions.
- `final.xml`: expanded producer/projection/export/privacy cohort, 20 passed,
  zero skips, 23.855s on both databases. Includes strict copied metadata/map/cell
  rejection and numeric timestamp rejection; the latter intentionally produces
  Pydantic's unsafe-copy serializer warning before rejection.
- `actual-absent.xml`: final actual-acquisition empty-subwindow refinement,
  2 passed, zero skips, 3.994s on both databases.
- Whole repository Ruff and configured mypy: clean (1,341 Python sources).
  `git diff --check`: clean. No broad baseline or aggregate run.

Actual acquired 61-day daily rows give September 100 clicks/$100 and August explicit
zero, with complete day coverage. A sparse actual response produces partial
subtotals; an actually empty requested subwindow produces null/unavailable.
Missing any of the five required raw aggregate cells rejects publication.
After-sidecar-insert failure rolls back all effects; immutable historical
receipt/presence remains readable after a later import. Populated lifecycle export
works; semantic privacy erasure removes receipt and sidecar.

Retained failed logs are not hidden: the first SQLite test helper passed a string
rather than a completion object to `read_presence` and referenced the wrong
Campaign attribute; both were fixture defects. A later privacy assertion incorrectly
expected raw sidecar deletion alone to invalidate the independent generic receipt.
The corrected assertion verifies corrupt traffic is rejected by `read_presence`,
while semantic privacy erasure invalidates/removes both domains. This distinction
is intentional: a future owned traffic reader must read BOTH receipt and sidecar.

## Remaining Work And Boundaries

No migration, owned traffic reader, proof/bundle integration, composer, capability
registration or runtime activation is included. The next slice must bind this graph
against the exact selected aggregate/current privacy and full retained SQL manifest,
then pair traffic with selected counts/value. This package alone does not close Q01
or provide a no-conversions diagnosis. No legacy Google normalization behavior was
changed. No live provider calls, credentials, provider completeness guarantee, cost
finality or advertising authority were introduced. No owner policy decision is
needed for the next already specified engineering slice.
