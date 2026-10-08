# Owned Window Reader — Frozen Implementation Package

Reviewed proposal `04aafcd` is accepted for the bounded reader package. Follow
[its concrete interfaces and acceptance](planning-owned-window-reader-contract-proposal.md)
and the separately frozen [private evidence contract](planning-window-evidence-contract-v1.md).
The reader consumes only the frozen `KnownWindowGap` value interface; it does not
modify private evidence models. Parallel preparation is allowed against that frozen
interface; final checks require the independently reviewed contracts implementation.

Implement `app/planning_documents/window_reader.py`, the optional private
presence-context parameters in retained_sources, focused tests and ledger. Keep
existing default context behavior, policies, adapters, composer, routes, settings,
source digest formulas and legacy fixtures unchanged. No migration or live IO.

Clarifications:

- `OwnedWindowReadContext` is a context manager with an idempotent `close()`.
  Preparing failure must remove installed event observers; `__exit__` closes on
  success or failure. Reads after close reject. Never rely on garbage collection.
- Guard transaction/completion/pending-state/source/catalog freshness before
  consulting a cached original as well as on underlying presence-cache reads.
  Check supplied ORM completion state before any populate-existing refresh can
  erase a mutation. A cache hit must not bypass the current ownership callback.
- Hooks reject nested transaction lifecycle and ORM flush attempts for this new
  context only. Raw SQL mutations/provider IO remain prohibited caller behavior,
  not a promised sandbox of arbitrary Python. State this limit in the ledger.
- Preserve actual owned current reader, manifest and source checks. No temporary
  report-header date replacement, presumed trusted DTO constructor, broad exception
  to gap conversion, or whole-graph pass to the pure projector.
- Do not broaden existing v2 call sites to use the optional cache in this package.
  New reader usage exercises it; old callers retain the None path and bytes.
- Default application still rejects policy v3. This package cannot claim customer
  window/comparison support, final API integration, whole-product qualification or
  live readiness. The next adapter/composer package remains to be defined and tested.
