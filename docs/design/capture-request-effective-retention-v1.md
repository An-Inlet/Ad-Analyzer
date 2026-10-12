# Capture Request And Effective Settings Retention — V1

Baseline `548c351`, local offline only. This is a concrete capture-flow prerequisite:
`SelectedCaptureRequestV1` retains attribution and a query-profile digest, but no
readable requested settings. Google acquisition already sends no attribution overrides;
the captured unknown basis does not record that absence. Saved plans retain only that
same basis. The next social candidates cannot safely overload it with request flags.

## Bounded Shared Interface

Add a strict immutable settings record with its own version, a finite profile ID,
count meaning, report-support state, value-unit state, allowlisted requested settings
and effective attribution. Existing Google conversions/all-conversions profiles are
distinct; the three social profiles from `social-selected-event-semantics-v1.md` are
explicitly unverified/unsupported. No generic registry, table, route or provider added.

Requested fields retain Meta action-report-time, unified-attribution flag and exact
attribution-window tuple (including absence). Their names never imply effective
behavior. Deprecated/ignored flags may be represented as requested historical facts,
with explicit ignored labels, but cannot qualify a social profile. Retired view-window
requests cannot produce a supported result. Non-Meta profiles reject Meta-only flags.

Initial effective attribution is always the existing fully unknown provider-default
basis. Known effective settings require a future concrete evidence contract, not a
boolean assertion or requested flag. Enforce exact equality with the enclosing request
attribution so a caller cannot smuggle an inconsistent effective value through either.

Google value units document the existing parser's account-currency-major input and
micros output, without expanding semantics. Social value units remain unknown and
cannot supply present MoneyCell values. Social report combinations cannot claim
supported capability; unsupported/unknown cells remain exact nonnumeric states.
Bind profile to platform, API, event and metric family; reject arbitrary labels,
grouped/app substitutes and owner claims beyond the actual advertiser.

## Version And Historical Boundary

- Existing request/capture v1 remains exact readable canonical JSON; optional settings
  omitted entirely when absent. New settings require requestv2 and capturev2, with
  coherent request/capture tags. Existing request/fact/capture digest domains retain
  their historical definitions; explicit tags/settings participate in canonical hashes.
- Only existing Google acquisition emits new request2/capture2 now. Its HTTP queries
  and authorization/read-only policy remain unchanged. No synthetic social producer.
- Original captures are never enriched on read. Settings project exactly into retained
  provenancev2; old captures still project provenancev1 without a new key.
- Saved plans containing provenancev2 require plan-versionv3. V3 allows a mixture of
  old/new capture provenance, requires all captures typed and at least one settings-
  enriched capture. V1/v2 cannot disguise new settings. Existing historical v1 bridge
  and v2 rules remain; legacy payloads/digests unchanged.
- Shared storage, replay, archive and exact historical capture reprojection enforce
  those distinctions. Forward migration0093 replaces only the capture insert-binding
  trigger to admit exact request1/capture1 without settings or request2/capture2 with
  settingsv1. It preserves scalar ownership/byte/FK/immutability/privacy fences and
  does not change tables, columns or historical rows. Frozen0091 remains unchanged.
  Downgrade refuses while any non-v1 capture remains; no automatic erasure. Existing
  bounds remain intact.
  Old readers reject new formats. Reader-first upgrade, suspended generation during
  transition and reader-capable rollback floor extend to capture2/provenance2/plan3.
  No lossy conversion, rewriting, row deletion or old-image rollback is implied.

## Customer Review And Acceptance

Saved review displays requested settings separately from effective unknowns, exact
profile/support/unit states and limitations. Legacy metadata remains honestly labeled;
Meta request-contract provenance alone cannot be displayed as effective attribution.
Display validation rejects contradictory settings/versions and clears invalid views.

Before implementation retain genuine pre-change capturev1 and planv2 JSON fixtures
with fixed hashes/digests. Focused regressions: strict settings/profile/version binding,
ignored flags never effective, unsupported combinations and unknown money units reject,
legacy exact readers/digests, capture storage/archive roundtrip on both databases,
actual Google acquisition→plan/current/history/export/replay/browser, lossless historical
projection and tamper refusal. Existing storage/kernel inventory and version tests
cover modified parsing/serialization boundaries. No broad aggregate rerun; full Ruff,
configured mypy, exact cases, separate SQLite/PG gate, original failures and resource
floors preserved. Independent source and evidence review required.

Retain the precise official evidence gaps in the checkpoint: Meta v26 exact report
field/grain/window combinations, row-scoped effective settings/counting mode; TikTok
v1.3 supported metric/dimension combinations, monetary units/precision/scaling,
status filters at campaign/day grain, and account/ad-group effective settings. No
omitted-row/field-as-zero contract is established. Both owner retention and artifact-
sharing decisions, six human judgments and all live/remote/spending holds remain.
