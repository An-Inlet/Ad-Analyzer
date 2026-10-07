# Linked Push Configuration Consent

`LinkedPushConfigurationDocumentV1` is a separate strict document in
`app/publication/tiktok_linked_review_contracts.py`. It must be stored under its
own schema discriminator in the existing owned configuration-review JSON table;
it is never parsed as a legacy social v1/v2 approval. No schema migration is
needed. Storage, exact approval, and current-provider validation implementation
are still pending at this interface checkpoint.

The document binds the owned source catalog request, named option, exact server
requirements/wording, owned identity and advertiser capability observations,
full linked configuration and its digest. The answer requires four explicit true
booleans: reviewed video/cover, commercial music rights, creation of a new linked
post, and ads-only visibility. Numeric truthiness is rejected. `linked_rights_digest`
binds request, requirements, answer, media and identity. The configuration must
carry that digest and the two exact observation digests.

Only contract_test is supported. AVAILABLE alone is insufficient: explicit
non-GPPPA and can_push_video=true observations are required. Missing capability
values stay unknown. Ads-only ON remains the sole supported visibility, so unknown
ads-only flags never become permission for OFF. BC owner publishing permission
must still be independently qualified by the runtime; this consent and can_push
alone do not prove it. All financial and original-session checks remain separate.

Forward coordinator dispatch will require a current linked configuration validator
and exact owned stored confirmation. The new runtime transport/context ports default
to None. Historical social v1/v2 documents remain readable without reinterpretation.
Export must add this exact document to the strict configuration-review union and
retain existing scalar ownership/digest binding. No broad raw-JSON fallback is
permitted. Existing attempted receipts, holds and reconciliation do not depend on
new forward eligibility.

Five pure tests pass: roundtrip, old-schema rejection, changed wording, explicit
capability denial despite rehashed commitments, strict answers and live denial.
Scoped mypy on the contract/test modules and whole Ruff pass. This is a shared
interface, not completed storage/API/customer acceptance.
