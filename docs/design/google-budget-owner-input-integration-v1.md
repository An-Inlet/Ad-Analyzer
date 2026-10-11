# Google owner hypotheses: atomic input integration and refusal

Design only, based on integrated discovery `79ff5fc` and pure binding interface
`8f5b60b`. No implementation, test execution, input/API enablement or policy change
is included. The separate historical linked-receipt strategy below is parent-selected, pending
review of its exact pure port before implementation.

## Additive data and byte preservation

`requests.CustomerInputs.google_daily_budget_intents` becomes
`tuple[GoogleDailyBudgetIntentV1,...] | None`, defaultNone, max20.
`context.PlanInputRevision.google_daily_budget_intents` becomes the corresponding
`tuple[ResolvedGoogleDailyBudgetIntentV1,...] | None`, defaultNone, max20.
Both existing wrap serializers remove only this field whenNone, recursively in
requests/input revisions/documents. Explicitempty remainsserialized, distinct from
absent. Primitive intent modules already avoid imports of context/requests/ports;
keep that dependency direction. No witness/fullcatalog/session field goes in the
public input. Current caller-provided selection fields are not authoritative proof.

Strict request validation checks account subset and duplicate account/opaqueowner
pairs. Resolved validation checks unique fullaccount/owner pairs across scenarios;
the shared pure binding supplies exact proof checks. No duplicate may be silently
collapsed by a dict. Canonical privateV5 alone admits nonNone fields. V1–V4 reject
nonNone, includingempty, rather than dropping them. None leaves existing byte and
behavior paths untouched, including Q08.

## Resolution port and original receipt

New `google_budget_input_resolution.py` proposes:

```
resolve_google_daily_budget_inputs(
    *, inputs: PlanInputRevision, intents: tuple[GoogleDailyBudgetIntentV1,...],
    catalogs: tuple[CatalogEvidence,...], sources: tuple[SourceFence,...],
    principal: CustomerPrincipal, privacy_revision: int,
) -> tuple[ResolvedGoogleDailyBudgetIntentV1,...]
```

This is private pure resolution, not authentication. The caller has already loaded
catalogs with `catalog_receipts.resolve_input_catalogs` using original principal,
source locks and `_load`. Every new intent requires exactly one ordinary campaign
allocation in its named supplied scenario, hence one existing TargetSelector and
one original linked receipt. No owner-only read, new provider acquisition, client
receipt ID, cross-receipt search or newest-catalog fallback exists.

After ordinary `input_resolution.resolve` builds exact scenario TargetRefs, inspect
only that account's already-loaded catalog. For each candidate owner rebuild the
full strict owner witness, compute `owner_selection_id` with the actual principal
and source, and require exactly one opaque match. Then compare supplied observation
and facts digests against actual values and invoke the standalone intent resolver.
The caller's expected digest is never inserted into a synthetic witness or trusted
selection calculation. Resolve all intents in order; anyfailure aborts the whole
request. Pass the complete proposed resolved input/intents/catalogs/actualsources
and actualprivacy to `validate_google_daily_budget_input_bindings`.

`prepare` must not misrepresent unresolved requests as resolved inputs. It keeps
an internal prepared PlanInputRevision with the new fieldNone until ordinary
scenarios are resolved; the immutable request still carries the requestedfield.
The resolution result is revalidated with the actual resolved tuple (including
explicitempty). Do not persist the temporary prepared form. Ensure both existing
resolve callsites consume the identical verified resolution result, rather than
one silently dropping or recomputing owner fields without principal context.
Prefer extending the private `ResolvedInputCatalogs` result with resolved owner
intents (omittedNone) and passing them explicitly to final pure resolve; do not
add a process-global principal or weaken the existing resolve signature implicitly.

## Atomic create/edit and final receipt binding

`service._save_inputs` retains its existing creative/selected capability prechecks
before receipt replay. Add the new nonNone owner-input canonical privateV5 guard
beside those prechecks, also before replay; do not move legacy gates. Thus an exact
owner-input replay requires the same supported privateV5 configuration, while all
existingNone replay behavior is unchanged. Within that supported configuration,
its two exact receipt replay branches remain before new receipt lookup and return
the original immutable input even after catalogTTL passes. Changed request-key
payload or cross-plan replay still fails. After replay enforce ordinary goal
confirmation, input/version CAS and media/source guards before resolution. The first SQL phase
supplies real full-account fences and privacy to the pure binding. Its existing
created_at is the actual original admission instant, after original catalog
observation; never restamp it to make an old receipt fit.

In the final original-authority transaction, refresh the actual full source set and
privacy and require the prepared ticket values unchanged. `repository.save_input`
and `bind_input_receipts` remain one transaction. The latter reloads every original
receipt and repeats pure owner binding **before inserting links**, using exact
resolved inputs, freshsources and privacy. A subsequent failure rolls back the
new plan/head/input/request/link graph. Repeat expiry and final authority after
all inserts/flushes as today. No partial intent persistence, new ledger, or migration
is proposed in the admission slice.

`resolve_saved_input_catalogs` and `recheck_saved_input_receipts` repeat owner proof
binding on actual original loaded catalogs/fullticket sources/privacy. Even though
generation is refused in this slice, retained current input reads must never
silently downgrade missing owner proof to primitive hypotheses.

## Historical proof decision: explicit separate linked-receipt port

Actual `validate_retained_input_receipts` reconstructs CatalogEvidence from each
linked immutable CatalogReceiptRow plus its exact retained input AccountRef.
`InputCatalogReceiptRow` links only accounts referenced by exclusions/fixed/scenario
selectors. Unselected input accounts have **no retained original source-binding
digest/privacy fence**. The input stores their AccountRefs, not full SourceFences.
No-input-selector explicitempty also has no catalog links from which to recover
an original privacy epoch. PlanDependencyRow belongs to generated versions, so it
cannot supply an input-revision proof before generation.

The frozen pure validator requires exactly one source for every input account and
an exact privacy argument, even for empty intents. Calling it historically using
current source state, guessed privacy, or duplicated selected-account sources would
fabricate evidence and is prohibited. Reducing inputs.accounts in a temporary
copy would also change the exact historical input and is prohibited.

Parent selected the separate historical port, leaving active validation unchanged:

```
validate_retained_google_daily_budget_input_bindings(
    *, inputs: PlanInputRevision,
    intents: tuple[ResolvedGoogleDailyBudgetIntentV1,...],
    catalogs: tuple[CatalogEvidence,...], sources: tuple[SourceFence,...],
) -> tuple[GoogleDailyBudgetOwnerWitnessV1,...]
```

There is deliberately no privacy argument that could invite a fabricated value.
The SQL caller derives **exact linked-receipt sources** only from original validated
rows, then the pure port derives their single unanimous privacy value. Inputs,
accounts and goal stay unchanged. It shares the strict owner/scenario/exclusion kernel; it validates
all retained full AccountRefs but makes no claim of original source commitments
for unselected accounts. Require one exact catalog/source for every owner-intent
account, unique sources exactlymatching linkedcatalog accounts, uniform retained
privacy across those rows, original input/receipt admission-time joins, and no
current clock/session/provider read. Nonempty intents necessarily have a linked
catalog, hence a real retained epoch. For explicitempty with no linked catalogs,
require intents empty, catalogs empty, sources empty and no ordinary selected targets
(fixed/scenario/excluded); the SQL wrapper first validates its exact immutable
input/link graph through existing `_bindings`. Return empty witnesses as an explicit
no-owner-evidence result without claiming
an unrecorded privacy epoch. Current admission keeps the stronger full-source
validator unchanged. This is a distinct historical contract, not a mode flag that
can weaken active admission.

Alternative if full-account historical fences are required: introduce a separately
reviewed private immutable input-revision source proof with all original fences and
privacy, retention/erasure/export bindings and a schema plan. Do not smuggle this
into public input JSON or modify old receipt payloads. No such storage is currently
approved. Implementation must wait for review of this exact historical signature; the discovery
endpoint remains useful independently.

### Historical opaque selection commitment (mandatory SQL wrapper join)

The pure owner binding kernel preserves the opaque selection string; observation
and facts equality alone do not authenticate it. Therefore historical
`validate_retained_input_receipts` must also recompute each original opaque
selection from the **same exact validated CatalogReceiptRow** supplying its witness.
Use retained actor_id/session_digest/authenticated_at, original source/account/
privacy, composite digest, witness digest/owner and UTC reporting window. Compare
against the resolved intent.owner_selection_id before accepting historical input.
Actor must equal inputs.created_by, and the existing link/account/admission checks
remain mandatory. No current principal/session, paid status or currentTTL is used.

Narrow helper refactor proposed for discovery owner review:

```
_owner_selection_commitment(
    *, actor_id: Id, session_digest: Digest, authenticated_at: int,
    source: SourceFence, witness: GoogleDailyBudgetOwnerWitnessV1,
) -> str
```

Strictly validate scalar strings and nonnegative authenticated integer (notbool),
source and witness. Move the existing exact fingerprint payload unchanged into
this private pure helper. Existing `owner_selection_id(principal,source,witness)`
delegates with its already authenticated scalar values; historical wrapper passes
only values from the exact original validated receipt. This is hashing, never an
authority assertion: do not construct fake CustomerPrincipal/CustomerSession ORM
objects from historical rows. No private scalar enters public DTOs or logs.
Golden equality proves existing discovery commitments unchanged; historical tests
change session/authenticated/actor commitments independently and must refuse even
when observation/facts digests still match. Both current final-link and historical
wrappers must apply this commitment check, not just initial selector resolution.

## Generation refusal at every boundary

New cycle-free primitive guard `reject_google_budget_generation(value)` rejects
all nonNone values, includingempty, with a fixed error. It consults no source or
policy and imports neither context nor documents.

- `service.generate`: after owned input load/existing exact completed receipt replay
  and before GenerationTicket/external evidence acquisition, refuse nonNone.
- `DescriptivePlanComposer.compose`, `WindowPlanComposer.compose` and `_compose`,
  `SelectedPlanComposer.compose` and `_compose`, `CreativePlanComposer.compose`:
  strict input/ticket validation then sameguard before any proposal construction.
  Internal `_compose` methods are directly callable and must not be a bypass.
- `PlanVersion` invariant rejects nonNone under every currentlyregistered pair,
  includingV5; model_validate, canonical/digest and unsafe-copy revalidation inherit
  it. Existing documents cannot reinterpret an unsupported intent as ordinaryV5.
- Repository genuine save should fail through strict PlanVersion admission before
  writes, preserving existing exact completed replay/history behavior.

No defaultpolicy switch or V6 assumption. Later output support needs a distinct
reviewed semantic version and exact action/witness consumer before these gates can
be replaced. All existingNone documents retain their original canonical bytes.

## Ownership and bounded acceptance

Integration lane: requests.py/context.py/input_resolution.py/catalog_receipts.py,
service.py, smallnewresolution+generationguard modules, composer guardcalls,
documents.py, newfocusedtests and ledger. Pure author owns
`google_budget_input_bindings.py` and any approved separate historical port.
Discovery modules/helper remain unchanged unless their owner reviews a needed
amendment. No browser, main/router, metadata query or schema edits in this slice.

Required before freeze:

1. Pure Python/JSON nested request/input/PlanVersion omission/digest goldens forNone;
   explicitempty preserved in inputs but rejected by every generation boundary.
2. Actual original-session Q06 discovery→scenario→create/edit through privateV5;
   full shared members, independent scenarios, zero/currentamount/currency/child/
   exclusions/constraints and max20/duplicate negatives with exact no-row-delta.
3. Completed create/edit replay before expired lookup; changed request key, input/
   version CAS, newgoal confirmation, anotherowner/session, privacy/reconnect,
   mixedreceipt, malformed opaque selection and changed witness/facts refuse.
4. Fault after inputflush/before linkinsert and linkvalidation failure roll back all
   heads/inputs/requestreceipts/links. No native calls during admission or replay.
5. Historical input validation/export after receiptTTL and after newer catalog
   acquisition succeeds on exact original proof; corrupted/missing raw receipt or
   link, wrong account/source/privacy/member/digest refuses. Semantic erasure follows
   existing protected privacy graph; no private session/source fields exported.
6. Explicit tests for multi-account inputs with unselected accounts and emptytuple
   noselectors, based on the reviewed historical decision, not syntheticfences.
7. Existing Q08/legacyNone create/generate/read/export and completedreplay regressions;
   all production financial/execution/provider mutation counts remain unchanged.

Run SQLite first, then bounded bothDB with exact collection/evidence logs; no tests
are authorized by this design-only commit itself. No fullQ06/expert/live claim.
