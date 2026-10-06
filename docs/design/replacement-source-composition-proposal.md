# Replacement Source Composition Proposal

Reviewed frozen `a4fcd3a`. Proposal only: no new source implementation, profile,
financial release, provider calls or runtime activation. The [source matrix](production-spending-source-readiness.md)
and [native Google assessment](google-native-exposure-qualification.md) remain authoritative
about gaps. The [joint-envelope proposal](google-joint-envelope-proposal.md) remains separate.

## Smallest Remaining Implementable Plumbing

Implement an optional server-owned `ReplacementReader` compositor, not a native
financial guarantee producer. The existing [Google terminal reader](../../app/publication/google_request_terminal.py)
can establish completion of all retained exact successful original configuration requests.
The [replacement service](../../app/publication/replacement.py) still has no production
reader joining that evidence to independently qualified transition/portfolio evidence.

Proposed additive interface, subject to review:

```text
TransitionSourceRequest {
  exact binding, intent, before, qualification, replacement snapshot
}
TransitionCertificate {
  exact request digest
  source profile + revision [server allowlist, not caller assertion]
  source evidence digest
  observed_at, expires_at [fixed source epoch, <=5 minutes]
  semantics: current_proposed_delayed_no_effect_and_residual
  portfolio: ExposureEvidence
}
TransitionCertificateReader(request, now) -> TransitionCertificate | unavailable
GoogleReplacementReader(session_factory, actor/session authorizer,
                        transition_reader, allowed_profiles, clock)
  implements existing ReplacementReader
```

`TransitionCertificateReader` is an explicitly injected trusted server source port.
A syntactically valid certificate is not provider qualification. No default source,
fixture fallback, provider profile registration or customer submission endpoint ships
with this compositor. Live certificates require a separately reviewed provider-backed
source specification; contract scenarios remain simulation-only.

The compositor would perform the following checks:

1. Reconstruct current persisted mandate/account generation and full replacement ancestry
   with the existing owned terminal reader. Reject any missing, unsupported, timed-out,
   legacy or changed original request, including mixed ancestors.
2. Release only its independent session before blocking source IO. Never commit the
   coordinator's supplied session. Recheck current actor/session, mandate, generation,
   ledger high-water, holds and exact snapshot after IO in workspace-first lock order.
3. Require exact source request, qualification ID/revision/profile, state and intent;
   exact full mandate account set, currency, period, owner and target topology; finite
   explicitly qualified U/F/P and complete portfolio; and current policy eligibility.
   Reported high-water and held reservations come from the current ledger, not source
   instructions to reduce them. Replacement excludes only the exact predecessor hold.
4. Intersect certificate, qualification and policy freshness. Reject future observations,
   expired evidence, changed evidence and completion captured after the certificate epoch.
5. Emit the existing `ReplacementEvidence`, preserving every original request/fence.
   Closure means only `authoritative_request_terminal`, never later-effect impossibility.
   No hold transfer occurs in the reader; existing coordinator checks remain decisive.

### Exact Recheck And Evidence Epoch

`replacement.transfer()` requires `proof == document.replacement`. Therefore freshly
stamping `now` on every composed result would make a legitimate later recheck fail.
Do not weaken this equality or extend expiry. Use the immutable transition certificate's
original epoch and canonical closure content digest (profile, scope, binding, snapshot,
ordered exact request/fence/evidence tuples), excluding the terminal batch's per-read
observation timestamps. Fresh terminal authorization is still performed every time.
The certificate epoch must be at or after every included completion and receipt epoch.
A changed certificate requires new review. A source may return the same still-valid
immutable certificate; no stale fallback after source failure is permitted. Durable
certificate storage/cache is separate work, not silently added to this package.

Tests can prove composition, ownership, stable repeated reads within the unchanged epoch,
full-set/fence integrity, changed generation/role during source IO, expired/future evidence,
foreign currency/account/period, changed high-water/holds, null bounds, unregistered live
profiles, unavailable source, and timeout ancestors. These tests cannot prove native
financial guarantees. No schema or social request-byte changes are needed.

## Remaining Code Versus External Guarantees

| Item | Implemented | Still code work | Missing authoritative guarantee |
|---|---|---|---|
| Google successful original operation | Exact HTTP capture, durable owned reader, full terminal batch | Optional compositor above | None additional for this narrow successful-response assertion; unknown/lost responses remain unsupported |
| Meta/TikTok original operation | Mutation adapters and normalized receipts | Endpoint-specific provenance/capture and owned terminal reader, only after semantics review | Reviewed exact synchronous completion semantics; correlation IDs/readback are insufficient |
| Reported R and money | Metric imports, native diagnostics, ledger high-water | Versioned billing-basis adapter, adjustment/currency/period mapping | Compatible provider counter semantics; owner monetary promise must be explicit |
| Unreported U | Nullable evidence port and fail-closed arithmetic | Provider source once specified | Deterministic completeness/residual bound; an SLA is not that bound |
| Unchanged F | Bounded native inventory and owned context assembly | Qualified complete portfolio producer, including unsupported inventory families/history | Enforced future exposure boundary covering all owners and external changes |
| Proposed P | Operation adapters; replacement ancestry and atomic funded transfer | Provider transition certificate producer, then compositor | Bound covers old/current/desired, delayed or never-applied operation, delivery/reporting residuals; no CAS assumption |
| Writer boundary | Local mandate, audit, reservations and freshness guards | Provider-specific enforcement verification/invalidation once specified | Native prevention of uncovered new owners, cap resets/raises and competing writes throughout obligation window |
| Settlement | Retained holds and strict settlement ports | Native qualified settlement reader | Complete compatible cost through last possible effect, no remaining liability; request completion alone is insufficient |

The diagnostics adapters are real implemented code but provide no finite U/F/P. Approved
credentials would not supply missing semantics or build the remaining producers. Conversely,
new interfaces and passing fixture tests cannot close an external guarantee gap. Current
live blocker and disabled factories must remain unchanged.

## Minimal Owner Decision Package

- Decide the versioned monetary promise: served media, net billed media, or all-in cash.
  Recommend net billed media excluding taxes/fees only if it matches the product promise;
  make credit/refund treatment explicit. This is not approval to reinterpret existing
  high-water or holds. Engineering must first map each provider's compatible facts.
- Keep the strict ceiling. Do not ask for permission to replace unavailable evidence with
  daily budgets, reporting delays, dedicated-account promises or best effort.
- A restricted autonomous launch decision becomes concrete only after a demonstrable
  native preventive mechanism and supported account configurations exist. Present exact
  customer exclusions and enforced controls then. None is currently qualified.
- If shipping sooner is a priority, an explicitly recommendation-only release is a
  separate product scope decision. It does not complete autonomous optimization acceptance
  or permit account writes. Continue authorized offline engineering meanwhile.

No owner answer alone closes U/F/P or native prevention. Next engineering choice is the
bounded compositor above; native financial-source implementation remains blocked on a
reviewable provider-backed guarantee, not merely access or consent.
