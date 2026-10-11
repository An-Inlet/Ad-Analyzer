# Owner Retained Context: One Mandatory Validation With A Pair Restriction

Design only on d594cb9. Implementation is held pending the parent’s retained-stage
observer results and independent interface review. The first zero-case expiry was
after retained capture and before CAS; the separate after-CAS storage-pair proposal
cannot repair that observed failure. This proposal makes no causal or timing claim.

## Source-Proven Adjacent Boundary

Current V6 capture calls top-level PlanVersion validation, then the public owner
port's `_owner_document` (full validation + exactV6), immediately followed by
`_Context` (another full validation). No SQL, guard callback or clock sampling occurs
between those last two document validations. Recheck has the same owner/context
adjacency. Later shared-creative context, selected capture, current image metadata,
creative witness and repeat owner receipt validation cross fresh SQL/guard boundaries
and are explicitly outside this change. Top-level dispatcher validation stays intact.

## Private Constructor Delta

Only private `creative_retained_sources._Context.__init__` gains a keyword-only
restriction:

```
_Context(db, principal, document, now, *, required_pair: tuple[str, str] | None = None)
```

Mandatory ordering before touching db or principal:

1. Run `PlanVersion.model_validate(document)` unconditionally once and retain its
   returned value as `self.document`; unsafe copied/nested values are still validated.
2. If a restriction is supplied, require exact tuple shape/length and strict string
   primitives, and compare the checked policy/generator pair to it. A mismatch raises
   the same bounded `ValueError("exact owner review document required")` used by
   the owner port today, before now/context checks as in the original owner gate.
   This is an extra AND condition: it never authorizes a pair, skips a validator,
   renews time, or chooses a bypass mode.
3. Inspect only the checked document for the existing exact canonical selected
   descriptor, require its creative flag (closed V5/V6 pairs), and perform the
   existing strict aware-now validation. Unknown/mixed/future pairs still refuse.
   None preserves existing private-context behavior; even a supplied unknown pair
   cannot pass the descriptor.
4. Only then obtain and check the same clean Session/Connection transaction roots
   and initialize existing timing/authority state, unchanged.

Public V5 wrappers retain their exact refusal and error semantics; no public function
signature changes. The constructor remains private, with no validated-object token,
cache, callback argument, or reusable trusted-state mechanism.

## Two Owner Callsites Only

In `capture_owner_review_retained_sources` and
`recheck_owner_review_retained_sources`, remove only the immediately preceding
`document = _owner_document(document)` call. Construct `_Context` with literal
`(OWNER_REVIEW_POLICY_VERSION, OWNER_REVIEW_GENERATOR_VERSION)`, then use
`document = context.document`. All subsequent logic sees the fully validated
canonical result, not the supplied unsafe copy.

Keep `_owner_document` unchanged for historical validation and any other caller.
Keep whole dependency validation at its existing position after context construction
and before owner receipt reads in recheck, all before/after original receipt loads, complete catalog JSON equality, selected/image/selected/current witness checks,
READ_ROLES, original transaction roots, guard/error boundaries, final clocks and
five-second caller authority unchanged. No cross-I/O/pass/request reuse is introduced.

## Bounded Proposed Checks

- Wrong V5/future/mixed pair in each public owner port refuses before touching a
  no-SQL/no-principal sentinel. A required unknown pair cannot broaden the context.
- Malformed required-pair shapes and copied invalid document primitives/nested
  owner catalogs still refuse before SQL; strict UTC/DST/type requirements remain.
- Existing exact V5 context and public wrappers produce identical witnesses/errors.
- Genuine V6 nonempty/empty retained capture/recheck fixtures retain complete output
  and original receipt proof. Existing mutation, transaction replacement, revoked
  session, late expiry and missing-link cases remain relevant; select only bounded
  affected cases once implementation is approved, not an automatic full rerun.
- Structural assertion or an ordinary private validation helper spy can demonstrate
  one mandatory document validation at this context entry; do not add production
  Pydantic descriptor instrumentation or change observable application calls for
  measurement. No claim that a removed validation fixes the deadline incident.

Own only the private context constructor, these two owner callsites and focused
new tests/ledger. Do not change retained dispatcher, historical source, model
serializer, authority or storage-pair code in this slice. Any further optimization
requires new evidence and review.
