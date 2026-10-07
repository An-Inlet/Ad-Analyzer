# Google Runtime Assembly Frozen Ports

First implementation slice of [the execution assembly proposal](production-execution-runtime-next-package.md).
No existing planning, mandate, provider plan or financial-evidence schema is changed.

`app/production_runtime/contracts.py` now defines the strict
GoogleExecutionManifestV1, GoogleEvidenceDescriptor, GoogleExecutionEvidence,
RegisteredGoogleEvidenceSource, GoogleEvidenceFactory and GoogleOwnedContexts /
GoogleOwnedContextFactory. `configuration.py` implements the bounded canonical
manifest loader. Absence is unavailable, malformed/partial configuration fails
closed, proof fields cannot be submitted in JSON. No credentials are in this file.

Only Google creation/activation ports are implemented. Required manifest fields
pin source ID/profile digest/environment/APIv25 plus explicit activation/live flags
and credential/context lifetimes. Existing concrete HTTP adapters retain their
bounded implementation limits; the manifest does not pretend to configure unused
transport knobs. Creation configuration qualification will be the actual existing
Google read qualifier, not another injectable proof port.

The evidence registration is a trusted Python object with a descriptor and factory,
never an import path, arbitrary callable or proof payload read from settings. The
pure admit_source checks the descriptor before invoking any factory/transport.
A live manifest with a contract_scenario source always denies, including when its
live flag is true. A matching descriptor is necessary but not sufficient: existing
financial readers/coordinator still validate every fact, unknown bound, reservation,
period/account/currency and retained hold. Missing registry entry remains unavailable.

Evidence factories receive actual sessions, the original-session authorizer, its
explicit bound actor_id, and clock. They return exactly the existing creation
ExposureReader and ActivationExposureReader, retaining all arguments and semantics.
Their returned descriptor must equal the admitted descriptor before constructing
provider contexts. Activation uses the original parent reservation argument, not a
new exposure pool. No optimization/replacement/settlement ports are stubbed here.

Owned context factory receives actual sessions, original-session authorize+actor,
manifest and clock, returning a context manager whose context supplies publication,
catalog and activation contexts. It must recheck owned Google connection generation
and source under short private sessions before/after OAuth/native IO; original
identity is never global. An open context manager owns/cleans HTTP resources. Scope
passed by the caller is always revalidated; no credential is admitted from request
or persisted in proof. Constructors open no sockets.

Next actual assembly callable:

```
configured_google_execution(db, principal, provider)
    -> ContextManager[CustomerExecutionRuntime | None]
```

This uses db.get_bind(), pinned manifest/settings, trusted source lookup and the
concrete owned context factory. Customer API dependencies must yield/close it and
continue using their existing original-session-bound coordinator wrappers. Legacy
explicitly injected runtimes remain usable in their existing tests; ordinary new
acceptance does not override runtime getters.

Shared CreationRuntime currently requires all provider transport slots. Preserve
that interface: existing inert concrete social adapter constructors can occupy the
unused slots, with a Google-only social-context gate that always rejects before IO;
no social catalog/configuration capability is exposed by this bundle. Do not add
future callable placeholder ports or treat these slots as enabled Meta/TikTok.
A supplied social request must fail the server provider gate before its evidence
reader/adapter, not merely rely on the UI hiding a choice. The future provider
slices will replace that gate with their real qualified assembly.

Default server source registry is empty. Tests register an explicit trusted
contract_test implementation and inject only underlying HTTP transport for provider
reads/writes. This tests actual configured durable create/approve/claim/pausedgraph/
activation/reconcile with no seeded reviews/attempts/holds/receipts; it is not live
financial qualification. Worker automation and other-provider assembly remain
tracked followups, not claimed by this first freeze.
