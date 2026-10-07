# Owned Optimization Inventory And Admission

`production_runtime.optimization_catalog.OwnedOptimizationCatalogHTTP` accepts an
original-session owned context reader, trusted `OptimizationCatalogAdmissionReader`,
explicit environment, transport and clock. Its `read(OwnedOptimizationInventoryRequestV1,
now)` returns `OwnedOptimizationCatalogRead`: ordinary opaque TargetCatalog plus exact
candidate/qualification/state-digest provenance keyed by option ID and fixed exclusion
counts. Callers must reauthorize original session and current goal/source/period under
their final database fences before persisting this result. This module has no database,
runtime/getter/API registration, consent, mutation or financial reservation side effects.

The current confirmed-goal or original-mandate money horizon is supplied by the owned
caller, never invented here. Existing non-authorizing account observation requests
carry the exact scope, timezone, currency and period into actual Google/Meta inventory
collectors; no fake mandate is constructed for bootstrap. Returned qualifications must
match the exact environment, scope, target and money context, be fresh and unresolved-
free. No admitted qualification means no current-state option. Native inventory alone
never creates qualification IDs or financial permission.

Inventory completes before selection. More than50 campaign rows rejects, without
silently truncating. Existing collector page/row/HTTP limits remain, with an additional
60-second elapsed limit,1000 wire calls,16MB total wire bytes and1MB per response across
inventory, separate names and current-state reads. Shared transport lifetime belongs
to the enclosing request. Errors return a fixed sanitized exception, never a partial
catalog. Names come from actual scoped provider name reads; missing/oversized names
are excluded, without native-ID fallback or modifying existing collector digests.

Google supports only independently owned, single-reference standard daily Search /
Manual CPC campaign budgets in this slice. Meta requires explicit campaign-level
budget ownership and known disabled sharing/scheduling/rebalancing flags. Existing
current-state adapters retain their stricter unsupported-feature checks. Readback
must retain the complete original inventory target topology (including Meta children)
and Google native budget resource; drift rejects the whole read. Unsupported owners,
missing names, absent admission and explicitly unsupported states yield fixed reason
counts, not financial proof. A completed offered catalog is not a complete liability
inventory or atomic provider snapshot.

Credentials are freshly resolved around inventory, name, admission and state reads;
clock/expiry bounds are checked throughout HTTP streaming and after blocking callbacks.
No mutable provider payload is accepted from customers. No new source is registered
and no default numeric operating policy is installed. Live/runtime and customer
consent assembly remain separate packages.

Validation:157 focused tests passed in1.37seconds across the new composed catalog,
Google/Meta native inventories, Google/social current-state HTTP and frozen runtime
contracts. New scenarios cover actual named options/provenance, admission-none,
wrong environment/money/unresolved facts, revocation, elapsed time, changed topology,
terminal/cycling pagination, overflow, absent labels and unsupported ownership.
Whole-repository Ruff passed; mypy over app plus the new tests passed453files;
whitespace check passed. No Full, database, live provider, remote or deployment action.
