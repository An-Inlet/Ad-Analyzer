# TikTok Configured Runtime Contract Freeze

This package implements the typed contracts and pinned file loader from
[the approved design](design/tiktok-configured-runtime-parity-ports.md). It does
not assemble a runtime, register evidence, implement native catalog decoding,
install customer endpoints, or qualify live execution.

## Concrete Interfaces

`app.production_runtime.tiktok_contracts` exports:

- `TikTokExecutionManifestV1`: explicit environment, pinned `v1.3`, evidence and
  configuration digests, activation/live flags, required bounded credential minimum
  remaining lifetime and context lifetime. No numerical product policy defaults.
- `TikTokEvidenceDescriptor`, `TikTokExecutionEvidence`, and
  `RegisteredTikTokEvidenceSource`: existing configuration, creation-exposure and
  activation-exposure reader ports. Optional `decoded_contract_catalog` accepts
  `SocialCatalogReader` only for a `contract_test` / `contract_scenario` descriptor.
  It is not a native identity/pixel response decoder.
- `admit_tiktok_source(manifest, registered)`: pure identity check; never constructs
  the evidence source. Always denies live admission while native discovery remains
  unverified. `registered_tiktok_evidence(source_id)` returns `None` by default.
- `TikTokCatalogContext`: owned TikTok account, exact request digest, expiry and
  excluded secret token. This is a reserved native-read contract, not a reader.
- `TikTokOwnedContexts.catalog(request, now)`, `.publication(request)`, and
  `.activation(request)`, plus `TikTokOwnedContextFactory`: typed protocols only.
  The eventual implementation must validate current original-session authority,
  source ownership and generation around IO. No implementation is supplied here.

`app.production_runtime.tiktok_configuration` exports:

- `TikTokConfigurationBundleV1.from_document(value)`: exact one-to-one TikTok
  profile/requirements mapping, explicit `cover_review_required=true`, nonblank
  reviewed wording, bounded profile count, USD/exponent-two initial subset. Existing
  social profile and requirements schemas/hashes are unchanged.
- `load_tiktok_execution_configuration(manifest_path, expected_manifest_digest,
  bundle_path)`: returns `(manifest, bundle)`, or `None` only when all inputs are
  absent. Partial/malformed/oversized/duplicate-key/mismatched-pin input raises the
  sanitized `TikTokRuntimeConfigurationError`. Manifest input is bounded to 16 KiB,
  bundle input to 64 KiB. The manifest digest pins the bundle transitively.
- Bundle accessors deserialize defensive copies from owned canonical bytes. Nested
  customer-profile mappings/lists cannot mutate the configured snapshot.

`app.production_runtime.tiktok_transport.tiktok_execution_transport(manifest)`
rejects contract-test before constructing a real transport. The real transport
boundary uses retries zero and no environment proxy configuration; no caller is
wired in this package. Source admission independently blocks every live manifest.

## Remaining Implementation Boundaries

No credential lifetime is inferred from a context lifetime. Future owned context
construction must reject unknown grant expiry unless a separately reviewed existing
validity contract proves the request safe; this package supplies no such proof.

The required `tiktok_native_catalog_parser_unverified` blocker and
`tiktok_decoded_contract_only` evidence discriminator remain unchanged in existing
`SocialCatalog`. Test scenarios may supply a decoded contract object, never live
provider proof. Native identity/pixel response evidence, financial qualification,
owned contexts, lazy composition, actual API and TLS journeys remain pending.
Google and Meta files, settings, plan hashes and registrations are untouched.
