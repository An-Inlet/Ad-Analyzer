# Q08 Composer Consumer Plan

Design only on `0ec485a`, dependent on approved `creative-q08-empty-proof-contract-v1.md`.
No production edits or test execution; standalone shared types must freeze first.

## File Ownership And Ports

- Contract lane: `catalog_evidence.py`, unchanged `ports.py` reexport,
  `empty_catalog_contracts.py`, additive `creative_production_contracts.py` fields,
  extraction/omission goldens. No changes from this consumer lane.
- This lane: `creative_composition.py`, `selected_composer.py`, new isolated pure
  composer tests and ledger only.
- Root: `empty_catalog_validation.py` helpers
  `validate_empty_catalog_proposals(...)` and
  `assert_empty_catalog_bindings(proposals, catalogs)`, document and repository
  invocation, actual API/historical/substitution qualification.

Exact shared constructors consumed: `EmptyDeclaredCatalogWitnessV1(
 catalog_evidence: CatalogEvidence, prerequisite_action_key: Key)` and
`CreativeProposalV1(..., target_basis="observed_empty_account",
 empty_catalog_witness=witness)`. Existing campaign constructors stay unchanged.

The composer extends only the approved keyword-only parameter
`account_prerequisites: tuple[ManualAction, ...] = ()`. Strictly revalidate each
passed action; do not accept a mutable/caller-authored trusted flag. The selected
composer passes its actual `tuple(actions)` immediately before creative composition.
No additional source read or changed authority/expiry interval is introduced.

## Exact Branch And Action Construction

Keep existing nonempty campaign branch and ordering unchanged. Only the no-included
campaign branch considers preparation, and only if the entire supplied composite,
native and metadata entity sets are empty. A nonempty excluded catalog, orphan
children, unavailable/unrecognized scope or missing prerequisite remains deferred.
Malformed supplied models still fail existing validation: do not blanket-catch
ValueError from the entire composition or turn corruption into an absence gap.

Eligible inputs require Meta, exact zero ceiling, typed product, at least one
witnessed image, explicit positive global capacity and no unresolved constraints.
Obtain the unique actual investigation action with exact account target,
`review:account_<account_id>` key, catalog evidence key, no native budget or fields.
Its key goes into both the witness and new action prerequisites. Construct the
witness from the exact original collected CatalogEvidence; no reconstructed native
inventory or invented query identity.

Use a separate private `_account_preparation_proposal` rather than changing the
existing campaign `_proposal` output. This produces one account-scoped creative
review/brief and existing image production metadata, consuming the same global
slot and action priority limits. Copy text explicitly describes no campaigns
observed **in the declared query**, never provider-wide emptiness or no prior spend.
Steps cover product/offer/rights verification, inspection of the owned image,
factual draft concept, destination checking and a record of measurement questions
for later supported evidence. No buying, launch or campaign-creation instruction.
No statement that the zero advertising budget covers labor or production costs.

After assembling the composition call root's
`assert_empty_catalog_bindings(result.proposals, catalogs)`; campaign-only results
remain a no-op for this additional helper. Repository independently repeats this
binding against its own original collected bundle before any mutation. Root's
PlanVersion validation binds retained witness, prerequisite, images, zero inputs
and UTC times, without relying on a composer assertion alone.

## Focused Qualification Once Types And Root Helpers Freeze

Pure positive uses genuine existing V5 inputs and actual-shaped recognized empty
catalog, owned image basis, exact actual account investigation and canonical policy.
It checks full account/advertiser/source/observation witness equality, prerequisite,
all zero spending fields, factual copy/restrictions and one global slot.
Negatives cover positive ceiling, absent product/image/capacity/prerequisite,
foreign/mismatched/duplicate prerequisite, nonempty excluded catalog, orphan child,
unavailable/unknown scope and capacity exhaustion. Fail/defer distinctions follow
model corruption versus recognized ineligible input; never invent a valid witness.
Existing campaign output bytes/digests must remain identical, including nested
serialization defaults, not merely equivalent descriptions. Actual API baseline
and later behavior qualification remain root-owned, with separate artifacts.

No fresh-provider-absence guarantee: currentness remains the existing persisted
source/privacy/authorization fence checks. A new live query is not introduced by
this slice. Historical validity uses the immutable saved witness independently of
any later catalog. No activation/default-policy change or full Q08 claim.
