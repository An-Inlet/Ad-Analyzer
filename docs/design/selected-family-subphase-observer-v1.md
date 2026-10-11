# Selected-family subphase observer03 contract

Source-only proposal, no implementation or measurement authorization. Extend reviewed clean observer02 c5fe29f0 on unchanged9fd75ab application source. Preserve complete measure02/freeze43696983 and truncated01. This is localization of an unresolved measured subtree, not an acceptance retry or production repair.

## Fixed additions

Add exactly five ordinary function families, only while an existing save span is active:

| Label | Definition | Frozen alias bindings |
| --- | --- | --- |
| selected_historical | app.campaign_performance.selected_storage.historical_capture | app.planning_documents.selected_plan_history.historical_capture; app.campaign_performance.selected_export.historical_capture |
| selected_scope | app.campaign_performance.selected_storage.current_scope | app.google_connections.selected_owned_context.current_scope; app.google_connections.range_publication.current_scope; app.google_connections.selected_customer.current_scope |
| selected_aggregate | app.campaign_performance.selected_storage._aggregate | app.campaign_performance.range_receipts._aggregate; app.google_connections.selected_owned_context._aggregate; app.google_connections.selected_customer._aggregate; app.google_connections.selected_acquisition._aggregate |
| aggregate_current | app.campaign_performance.aggregate.read | service.read_current imports this dynamically inside its non-Meta branch; no persistent read alias |
| retained_reporting | app.planning_documents.retained_sources._reporting | app.planning_documents.selected_plan_retained._reporting |

The fifth family is needed to distinguish legacy aggregate/presence/source commitment work from selected/traffic reconstruction inside each proof, not to broaden profiling arbitrarily. Do not add per-fact, per-row, Pydantic, flush, or generic SQL-call wrappers.

Replace only observer inventory module resolution with explicit full module names; no arbitrary module input. Preflight the entire fixed binding inventory using inspect.getattr_static, exact FunctionType and alias identity, no duplicate targets, before any replacement/handler/listener. Existing service keyword signature/call-shape checks remain. Frozen source review must confirm the aliases listed above, including bindings not exercised while save_active. Dynamic imports after patch obtain the same wrapped definition. Restore every exact original and leave another plugin's replacement untouched with incomplete flag.

## Accounting and interpretation

Use existing frame tree and deepest-span SQL assignment without algorithm changes. Every wrapper calls the original once, preserves returned object/original exception, uses real clocks, and suppresses only observer recording failures. No args, SQL text, row values, IDs, paths or exception strings retained. Fixed event handler remains operation-wide and independently bounded. Original authority guards, both selected-current passes and all retained proof rereads stay unchanged.

selected_historical is **mixed**: it includes batched historical SQL plus pure parsing, canonicalization and cross-node validation. Subtracting SQL duration does not produce a rigorously pure CPU time. selected_scope and selected_aggregate overlap by nesting; only direct-child exclusive partitions are disjoint. aggregate_current invokes current_scope through authorization callbacks; those appear as nested children, not an independent additive cost. retained_reporting captures its own current-report and presence work. Unwrapped time remains explicit residual.

A useful result separates repeated historical reconstruction from repeated current ownership/aggregate validation, with counts for those exact families. It still cannot attribute cost to a particular model validator, infer database contention, prove every same-row read redundant or justify bypassing fresh checks.

## Bound estimate, no cap increase

The one-Google chosen-capture positive source path gives the following static estimate per successful fresh generation, excluding unrelated pre-save/history/replay work because wrappers remain save-scoped:

- Each of two selected-current passes:4 selected graph/historical reads;7 aggregate validations (4 selected+3 traffic);25 current_scope invocations (4 selection+3 per aggregate);9 aggregate.read invocations (7 aggregate+2 reporting);2 reporting commitments.
- Selected-retained:4 graph/historical reads;8 aggregate validations;28 current_scope invocations (4 selection+3 per aggregate);12 aggregate.read invocations (8 aggregate+4 reporting);4 reporting commitments.
- Added total:12 historical+22 aggregate+78 scope+30 aggregate.read+8 reporting=150 frames. Combined with observed02's56 gives206, below512. Allow unexpected branches to consume the existing bounded remainder; do not assert this source estimate is measured coverage or a universal maximum. Four-operation/32-save/512-frame/128-save-final/256KiB bounds remain unchanged. Expected report is comfortably below the byte cap; if any bound nevertheless fires, mark incomplete and stop attribution, not increase limits or rerun automatically.

The original two selected passes and four retained pin proof bodies remain separate; no61-day SQL N+1 is assumed. Facts and daily manifests are already batched. Caps are never enlarged to hide insufficient accounting.

## Proposed qualification boundary

After contract/source review, external Ruff/compile and a new immutable manifest may reuse the exact prior collected normal postgres-owner node only if application/tests and fixed fixture hashes remain identical. Fresh observer plugin hash, full source manifest, unique report/log/XML/temp/cache/resource/result paths and one-run authorization are mandatory. Retain --assert=plain, --show-capture=no and junit_logging=no; fixed safe logger event capture remains the only log-derived report data. Use unchanged reviewed runner with original exit persisted before XML/report parsing and postrun source/Git-state checks.

One separately authorized changed-observer measurement, no retries. Success is not acceptance or R01–R03 closure. A subsequent repair requires a concrete mechanism supported by this localization and a separately reviewed semantics-preserving implementation contract; no authority/freshness/clock change follows from this document.
