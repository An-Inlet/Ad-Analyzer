# Inlet Private Media Storage

B14 adds a runtime Google Cloud Storage adapter. It is implemented and tested offline;
no bucket, runtime identity, IAM grant, deployment, or live upload has been created or
verified. Default `AD_ANALYZER_MEDIA_STORAGE_MODE=disabled` is unchanged. Enablement
requires an independently approved deployment with mode `gcs` and
`AD_ANALYZER_MEDIA_GCS_BUCKET` set to an existing private bucket. The runtime uses
Application Default Credentials; never place credential files in the repository.
The Google SDK endpoint is fixed to `https://storage.googleapis.com`; emulator mode
is rejected. Local development storage remains separate.

Every operation reads actual bucket metadata and requires both uniform bucket-level
access and explicit public-access-prevention `enforced`. `inherited` fails closed
because it alone does not establish the effective organization policy. This adapter
never provisions buckets, changes IAM/ACLs, emits public/signed URLs, or follows a
metadata-provided mediaLink. Customer authorization remains in the API/service;
storage keys additionally namespace workspace ID and validated SHA-256 digest.

Uploads validate the exact declared length and SHA-256 before calling the provider,
then use `if_generation_match=0`. A concurrent create/precondition failure triggers
verification of the existing object rather than overwrite. Successful uploads are
also read back and checked. Reads validate metadata length, bind a newly constructed
blob to the observed immutable generation, request a bounded raw byte range, enforce
a bounded output buffer, and recompute SHA-256. Storage supports at most 64 MiB;
image validation remains 8 MiB. No interface or database schema changed. Provider
errors become sanitized storage failures, with no unconditioned retry. Unknown write
outcomes can safely retry the same workspace/digest after content verification.

Privacy is checked again before returning downloaded bytes. These checks cannot
atomically prevent an external administrator from changing bucket policy during an
operation. Production review must ensure the runtime cannot change bucket policy,
objects are not otherwise exposed, and retention/versioning/soft-delete and storage
cost policies are agreed. SDK upload checksum handling is disabled because its
documented corruption cleanup can issue a delete. The adapter instead verifies SHA-256
before upload and after generation-bound readback; download CRC32C is additionally
requested where available. Failed verification is never accepted or automatically deleted.

## Deferred Deletion Contract

Before adding lifecycle deletion, define a durable, generation-bound object receipt
and deletion outbox with transactional reference checks across media and campaign
revisions. A future narrowly scoped delete operation must require workspace, digest,
size, and the exact stored generation, use a generation precondition, and distinguish
already absent from a replacement generation. Retention, soft-delete/versioning and
failed-upload orphan cleanup need explicit policy. This is a proposal, not implemented
cleanup; current unreferenced objects may remain. Do not configure time-only bucket
lifecycle deletion that can silently remove referenced media.

## Verification And SDK Sources

Offline tests exercise SDK autospec signatures and real SDK HTTP serialization with
a mocked transport: conditional creation/replay, generation-pinned ranged downloads,
workspace separation, policy failure/change, bounded writes/reads, wrong lengths and
hashes, malicious mediaLink, sanitized failures, and disabled/default factory behavior.
The adapter has no live-cloud verification. Full repository validation is coordinated
on the assembled candidate; this package records its focused checks separately.

Contracts verified against installed `google-cloud-storage` 3.16.0 and first-party docs:

- [Blob upload and download methods](https://docs.cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.blob.Blob)
- [Bucket IAM configuration](https://docs.cloud.google.com/python/docs/reference/storage/latest/google.cloud.storage.bucket.IAMConfiguration)
- [Public access prevention semantics](https://docs.cloud.google.com/storage/docs/public-access-prevention)
- [Uniform bucket-level access](https://docs.cloud.google.com/storage/docs/uniform-bucket-level-access)

## Package Evidence

Branch `codex/inlet-media-storage`, based on PR94 commit
`5f9a0d0d4d1d016135c54d3360b16e0800b6f6b6` (2026-10-06):

- `pytest tests/test_gcs_media_storage.py tests/test_campaign_review.py -ra` with the
  disposable PostgreSQL fixture enabled: **76 passed, 1 skipped**. The skipped
  SQLite row-lock race is covered by its PostgreSQL counterpart. Adapter tests mock
  the provider; campaign tests exercise SQLite and PostgreSQL.
- `ruff check .`: passed.
- `mypy`: passed, 289 source files.
- `git diff --check`: passed.
- Full suite/CI remains pending on this candidate. Parent coordinates assembled Full.

Remaining gates: independent code review, assembled Full, approved runtime identity
and private bucket configuration, live storage verification, generation-bound deletion
and orphan cleanup policy. No deployment or production completeness claim.
