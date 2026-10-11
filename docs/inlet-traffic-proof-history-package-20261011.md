# Traffic Proof And Historical Binding

Branch `codex/inlet-traffic-proof-history`, based on root `043342c`.

## Implementation

`selected_plan_retained.capture_selected_reporting_pin` now loads the exact owned
raw traffic graph after loading the selected capture pin. Successful graph reads
supply `traffic_pin=graph.pin()`; legitimate known absence remains `None`. No selected
input means no inferred latest traffic choice. Both existing proof reads and private
source/session/transaction guards remain in place. The existing complete proof
comparison therefore commits the optional traffic pin without a new runtime path.

`selected_plan_history.validate_selected_plan_history` validates each non-null
traffic pin after exact persisted document and complete historical dependency checks.
It invokes the pin-only historical reader, independent of mutable current metrics.
Only the reader's integrity HTTP409 is converted to the historical layer's fixed
`ValueError` contract, preserving repository and lifecycle-export behavior. Other
HTTP statuses, including future authorization failures, propagate unchanged.

No runtime, registry, capability, migration, bundle or paired-reader files changed.

## Tests And Evidence

`tests/test_selected_traffic_retained.py` uses the root's actual
`prepared_range_plan` fixture: 61-day raw MockHTTP acquisition, explicit owner event
confirmation, selected capture and real owned planning inputs. Positive history
uses a deliberately manual `PlanVersion` retention fixture with actual collected
references/proof and complete SQL dependencies. It is not a v4 composer or live
qualification claim.

Durable evidence: `/workspace/inlet-evidence/20261011/traffic-proof-history/`.

- `final.xml`: 60 passed, zero skips, 103.234s across new proof/history cases and
  existing retained/history/export regressions on SQLite and PostgreSQL.
- `expanded.xml`: four current receipt/sidecar mid-read race cases passed; four
  expanded history cases failed because the test edit had omitted the intended
  destructive SQL action. This failed artifact is preserved.
- `history-repair.xml`: all four corrected history cases passed, zero skips,
  25.570s. Actual direct validator, repository read and lifecycle serializer succeed
  before damage and reject missing receipt/facts afterward. Current metric rewrites
  do not invalidate intact historical traffic evidence. HTTP403 propagation is tested.
- Final whole Ruff and configured mypy pass (1,352 sources); diff check is clean.

The earlier SQLite fixture expected HTTPException/ValueError for a second-read
corruption; the established retained-source guard correctly raised
`RetainedSourcesChanged`. The assertion now includes that existing fail-closed type;
no production guard was weakened. Failed logs remain alongside terminal evidence.

The final eight focused behaviors have passing evidence across `expanded.xml`'s
four current-race cases and `history-repair.xml`'s four corrected historical cases.
No broad baseline, aggregate suite, hosted job, live provider call or push ran.

## Remaining Work

Root owns paired evidence collection and subsequent bundle/composer integration.
This package binds retained traffic evidence; it does not activate a policy or close
Q01 by itself. Original full campaign-map hashes remain saved opaque commitments
in pin-only history, as explicitly approved; retained fact ownership/native identity
and immutable receipt/header/facts are independently checked.
