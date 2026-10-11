# Exact Plan-Version Storage Pair

Design only, inspected frozen d594cb9. No implementation, test execution or observer
run. This is a small source-proven adjacent duplication, not an explanation of
R01/R02/R03 or measured attribution of save-boundary exclusive time. That timing
includes SQL, unwrapped work and observer overhead.

## Fixed Call Paths And Duplication

At `repository.save_generation` entry, ticket and candidate are strictly revalidated
and the actual evidence bundle asserts its ticket. V6 additionally runs
`assert_owner_review_generation_bundle` → `bundle.assert_ticket` → `_linked` →
candidate revalidation, linked original catalog derivation and actual owner-proof
validation. Later `final_sources` performs distinct selected/image/selected current
checks, then `recheck_owner_review_input_receipts` → actual original receipt resolution
→ `_linked`. Retained capture then performs separate original-owner/selected/creative/
original-owner current checks. These have different freshness/ownership purposes;
this proposal leaves every pass and its full validation unchanged.

Each V6 `PlanVersion.model_validate` includes `validate_owner_review_document` →
`linked_owner_input_catalogs` and `validate_google_budget_owner_review` → original
input/source/catalog binding → per-owner derivation/rebound/facts proof. Witness
construction, witness digest and facts digest themselves validate their inputs.
These paths explain static multiplicity, not their measured cost.

One strictly adjacent site is simpler: constructing PlanVersionRow currently calls
`candidate.digest()` and `canonical(candidate)` separately. `Frozen.digest` first
model-validates and JSON-dumps; `canonical` separately model-validates and JSON-dumps.
For V6 the PlanVersion wrap serializer additionally model-validates before emitting
fields. Thus these two adjacent calls each cross both an outer validation and the
V6 serializer validation. V5 lacks the new serializer revalidation branch, but still
performs the two independent outer validations. No callbacks or fresh SQL work
separate these two field evaluations in the source.

## Proposed Exact Private Port

In `storage.py`, add:

```
def plan_version_storage_pair(document: PlanVersion) -> tuple[str, str]:
    # returns (canonical_json, document_digest)
```

Require the exact PlanVersion model, not a caller-defined subclass/alternate digest
implementation. Call the existing `canonical(document)` exactly once, preserving
its complete `type(document).model_validate(document)`, current checked serializer,
legacy omission behavior, Unicode handling and MAX_DOCUMENT_BYTES check. Do not
replace model validation with model_construct, a trusted flag, a cache, a prior
digest, unchecked dump, or a previously prepared packet. Public `canonical` and
`Frozen.digest` behavior remain unchanged.

Derive the digest from those **same** canonical UTF-8 bytes using the existing exact
`common.fingerprint` domain protocol for PlanVersion:

```
sha256(b"inlet.planning-documents.v1\0" + b"PlanVersion" + b"\0"
       + canonical_json.encode("utf-8")).hexdigest()
```

Canonical JSON already uses sort_keys=True, separators=(",", ":"),
ensure_ascii=False, allow_nan=False. No second parsing/dump, Unicode normalization,
additional newline or different hash domain. Return only the two immutable strings;
no retained candidate graph, principal/session/fact, closure, cache or authority token.
The pair proves byte consistency and validated document serialization, not currentness.

Repository wiring: at the existing PlanVersionRow construction point, compute this
pair immediately before constructing that row and use both values. Keep it after
all existing input/actual-bundle/fresh-source/retained checks and first authority
final; do not move it outside the original fact window. Preserve conditional CAS,
transaction rollback, dependency capture, final DB clock and post-flush authority
checks. Do not change prior-version digest verification, replay validation or any
other storage callsite. No whole-document validation is removed from public entry
points; only the redundant adjacent storage serialization is eliminated.

## Unsafe Copies And Mutation Boundary

Frozen Pydantic models do not make unsafe model_copy or nested mutation trustworthy.
Every call must revalidate through canonical, including copied version/policy,
owner catalog flags/membership/time, proof/input/source mismatches and document size.
The V6 checked serializer remains intact. No successful result from a previous call
may be reused after mutation, across callbacks, SQL passes or requests.

After returning, strings remain internally consistent even if the supplied object
is subsequently mutated; that does not authorize storing a changed candidate. The
repository's existing candidate/proof/authority and rollback boundaries remain
unchanged. This helper adds no callback argument and does not suppress exceptions.
Any later failure still aborts the caller-owned transaction. Do not infer that this
small change resolves arbitrary concurrent mutation or original authority expiry.

## Bounded Qualification Before Integration

1. Pure exact equality across genuine existing V1–V6 fixtures: pair[0] equals current
   canonical(document), pair[1] equals document.digest(), and independently recomputed
   domain hash equals pair[1]. Include V6 nonempty and explicit-empty intents and
   existing legacy omission/golden bytes. No snapshot updates to hide differences.
2. Reject malformed/copied graphs that existing validation rejects: invalid version,
   mixed pair, unsafe owner native flags, mismatched witness/input/source, malformed
   timestamps and excessive serialized size. Preserve legacy acceptance semantics;
   do not introduce unrelated coercion changes. Exact model subclasses refuse.
3. Mutate an unsafe copy between helper calls: the next call rejects or produces the
   freshly validated changed pair as the existing canonical/digest contract dictates.
   Returned strings from the first call cannot change. No cross-call memoization.
4. Pure instrumented call count: existing canonical invoked once, and candidate.digest
   not invoked by the helper. This establishes duplication removal, not wall-time gain.
   Observer restores patches; no authority clock changes.
5. Existing real save fixture on SQLite/PostgreSQL: successful row stores exact paired
   bytes/hash; controlled failure at pair production after the existing CAS rolls back
   head/version/dependency/receipt effects. No retries, live providers or writes beyond
   disposable test storage. Replay/current/history read the original exact artifact.
6. Whole Ruff/configured mypy/diff plus bounded tests after source review and sole-slot
   authorization. No performance claim without separately reviewed measurement; keep
   normal five-second facts and post-flush expiry regression unchanged.

Own storage.py, the two row-value bindings in repository.py, and new focused tests.
Service/registry/receipt/currentness/portal code remain outside this slice. Review
this interface before implementation; the remaining API qualification and diagnostic
incident records stay independent.
