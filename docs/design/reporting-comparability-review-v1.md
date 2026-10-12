# Saved Reporting Comparability Review v1

Baseline: clean local `08573f2`. Implements Q09's customer visibility/recovery workflow,
not the missing Meta/TikTok selected-event producers or full three-provider Q09.
Default V3 and private V4–V6 remain unchanged; no new API, document schema, persisted
customer statement, provider call, policy registration or spending authority.

## Customer Workflow

1. Customer explicitly reads or generates a saved plan as today. Before Manual
   Actions, a prominent Reporting Comparability section says observations must be
   reviewed separately; matching currency alone does not make events comparable.
2. Each included account has a separate disclosure containing its original source,
   account/connection, requested primary/comparison periods, retained capture currency
   and time zone (or unavailable), and current displayed document freshness.
3. Separate evidence entries identify the exact requested interval, selected versus
   traffic versus legacy report basis, coverage, original read time, expiry and reasons.
   A capture interval is labelled acquisition coverage, never proof of complete days.
   Partial evidence coverage is not automatically a missing-day count: precise counts
   remain in the recorded measurement explanation, if supplied by that version.
4. Show existing measurement action rationales verbatim with exact target location as
   Recorded Measurement Explanation. This preserves original event resource/family,
   numeric observations, per-period coverage and gaps without parsing prose into new
   numeric fields, rankings, event equivalence or metadata assertions. These remain
   recorded explanations, not newly verified raw observations.
5. Clearly distinguish attribution click/view windows and report-time basis unavailable
   in this retained view, and event business equivalence unverified. Do not substitute
   today's selection or goal currency for missing saved facts. For legacy or unsupported
   social selected sources, explicitly say no qualified selected capture is retained.
6. The checklist directs the customer to verify business event meaning and metric
   family, click/view windows and report-time basis, account currencies/time zones,
   requested closed periods and date coverage, and fresh source lineage. Reacquire
   unavailable observations, explicitly revise inputs and generate another version.
   Historical versions remain historical; no checkbox grants equivalence or authority.

Disclosures expand/collapse locally only and reset on re-render/clear. No new network
requests or saved UI state. Existing workspace/session/late-response guards govern the
whole document. Established typography, palette, Title Case headings and text escaping
are reused. No public webpage change.

## Shared Renderer Interface And Validation

`appendReportingComparability(fragment, plan, {freshness, now})` is display-only and
called after the existing PlanVersion scope/authority/expiry checks, before actions.
It validates bounded account/evidence/proof references and joins using the full account
identity (workspace, account, connection, platform, connection version), never names.
If a proof is present, exact account coverage, capture selectors, source-fence binding,
selection head and aggregate scope must agree; malformed/foreign/duplicate data refuses
the whole render with the host cleared. It does not duplicate backend digest validation
or manufacture a currentness certificate. All source strings use textContent.

The view does not emit a “comparable” state. Evidence may be usable for an individual
qualitative review while unsuitable for cross-platform numeric comparison. No totals,
CPA, conversion rate, causal effect, forecast, ranking or budget transfer is calculated.
Displayed plan freshness and evidence expiry are explicit; neither proves attribution
or event equivalence. No new server persistence path: actual generation, current read,
historical export and idempotent replay retain their existing bytes and authority.

## Acceptance Cohort

- Renderer: legacy, selected Google observed count, missing/partial days, true zero,
  social selected unsupported, differing currency and unknown event/attribution states;
  no hidden numeric rankings or merged metrics. Bounds/scope/duplicate/hostile text;
  no stale content after invalid response, expiry, rerender or clear.
- Actual controller: repeated read, expand/collapse/reset, interrupted read, late response
  after workspace/session replacement. No comparison state survives a scope change;
  opening/closing the review causes no requests or mutations.
- Actual APIs/SQL: Google usable and deliberately missing selected day via raw synthetic
  acquisition, three owned platforms with social selected unavailable. Create/generate,
  current read/export and exact replay on SQLite then PostgreSQL; save original artifacts,
  validate PlanVersion/digest, unchanged source identities, no provider execution.
- Reuse prior handoff TLS journey on both databases with new review assertions to join
  actual reporting capture→new plan→generation→historical export to this customer view.
- Full Ruff/configured mypy plus focused pytest only. Resource floors/stop-on-failure,
  durable original exits/XML/source hashes and separate database gates preserved.

## Limits And Holds

Full Q09 requires genuine Meta leads/TikTok purchases with verified differing attribution
and complete original-source ownership/capture contracts; this package does not fake
those fixtures. In this saved schema, original event/attribution details are only partly
available; unknowns remain explicit. Independent source and evidence review required.
R01–R03 historical causes, six human judgments, retention and artifact-sharing decisions
remain outstanding. Local only: no push, hosted CI, live provider/model, deployment or spend.

Test-only acquisition seam: optional `missing_selected_day: date | None = None` passes
unchanged through `prepare_creative_q05_basis` → `prepare_creative_common_basis` →
`prepare_selected_common_basis`. It omits only that Google raw selected response row
before acquisition; no persisted capture/proof/document is rewritten. Existing defaults
remain unchanged. The partial case omits September 12, retaining September 15's 10
observations and the complete August window; no fake social selected facts are added.
