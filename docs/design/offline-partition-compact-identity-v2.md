# Offline Partition Compact Identity V2 — Proposal Only

Base `d85db66`. No code, workflow, consumer test, frozen checkout or database change.
Implementation and a third genuine collect-only attempt require separate review.

## Why V2

The terminal frozen W1 contains two campaign-media node IDs of 8,388,678 and
8,388,680 UTF-8 bytes and one 17,085-byte Omnisend node ID. V1 correctly rejected
its 16KiB node bound after genuine collection. No successful genuine full V1
manifest exists. The earlier strict-markers attempt and oversized-node attempt
both remain exit 4; neither becomes valid retroactively.

Do not increase the 32MiB collection or 64MiB JUnit artifact limits. Replace large
repeated identity strings with bounded identity records. The original raw aggregate
XML and collection logs remain authoritative retained artifacts. SHA256 plus length
is collision-resistant correspondence evidence, not literal identity attestation
or proof that an operator actually ran tests.

## Strict Private Shapes

All models remain frozen, strict, extra-forbidden. Versions become
`inlet.partition-collection.v2`, `inlet.partition-timing.v2` and
`inlet.partition-candidate.v2`; no silent V1 coercion or candidate fallback.

`CompactText` fields:

- `sha256`: lowercase 64 hexadecimal characters over exact UTF-8 bytes.
- `utf8_bytes`: positive strict integer, recording exact original byte length.
- `display`: deterministic leading Unicode-codepoint prefix fitting 256 UTF-8
  bytes. It is presentation only, never compared as an identity or selector.
- `exact_text`: required nullable string; present if and only if the original is
  at most 16KiB UTF-8. Verify its byte length, SHA256 and display whenever present.

The hook hashes its already-existing pytest strings without persisting repeated
large copies. There is no new raw-string payload field. Existing artifact limits
and 20,000-node bound remain; the XML parser still rejects over-64MiB input before
parsing. Large node length is metadata, not a request to allocate that many bytes.

`CollectedItemV2` fields:

- `node`: CompactText of actual `item.nodeid`.
- `file`: actual relative `.py` path captured before the callable separator;
  nonempty, at most 16KiB UTF-8, no absolute/traversal path.
- `junit_classname`: actual installed-pytest classname transformation, bounded at
  16KiB UTF-8 as ordinary text.
- `junit_name`: CompactText of installed pytest's `bin_xml_escape` result for the
  testcase name, preserving class scope and parameter punctuation.

Only the hook derives file/class/name from the actual node using the installed
JUnit helpers. Consumers cannot infer a file from a hashed node. For short exact
nodes, validate the captured mapping/file against those same helpers. For long
nodes, the captured file/class mapping is operator evidence subject to the same
commit/config/plugin provenance caveat; a DTO constructor cannot independently
recover or attest the original string. Do not guess dotted or `::` parameter IDs.

A node reference is the pair `(node.sha256, node.utf8_bytes)`, serialized as a
bounded `sha256:<hex>:<decimal-length>` key. Reject repeated references, repeated
JUnit identity triples `(classname, name.sha256, name.utf8_bytes)`, and any same
SHA256 accompanied by inconsistent length. Short exact-text contradictions reject.
If distinct long strings hypothetically collide with identical digest and length,
this scheme cannot distinguish them; explicitly retain that cryptographic caveat.

Collection metadata keeps commit, pytest version, exact configured scope, tracked
configuration path/hash and complete tracked historical provenance unchanged.
The manifest's ordered items retain original collection order. SHA256 is computed
on the same canonical JSON byte rules, now for the V2 schema.

## XML Binding And Candidate Output

The timing envelope still binds actual terminal commit, canonical collection hash,
raw XML hash and integer terminal exit. Version changes only; no invented timing.
The parser hashes the exact decoded XML `name` attribute's UTF-8, compares recorded
length, and joins it with literal classname to one captured JUnit identity. XML
escaping is handled once by XML parsing; pytest's captured name transformation
remains identical to its actual JUnit writer. Every testcase maps exactly once;
missing, extra, ambiguous or repeated identities reject. Retain all suite and
optional root counts, outcome/exit checks, Decimal bounds, failed/skipped/unknown
labels and XML declaration rejection.

Candidate fields use references, never expanded large node strings:

- `observations`: one mapping from compact node reference to status/time and
  passing-runtime-estimate flag.
- `current_shards`: existing deterministic whole-file groups, with ordered
  `node_refs`, file names, measured subtotals and outcome/unknown counts.
- `historical`: three literal bounded wrapper node IDs plus their compact refs,
  separate captured child-manifest hashes/counts and PIN proof. Child manifests
  keep existing exact 249-node validation, never join them to parent cardinality.
- `identity_index`: one compact metadata entry per reference, bounded display,
  file and original order; omit repeated exact node/JUnit names from candidate.

Prove disjoint/exhaustive union of all current refs and three wrapper refs equals
all collected refs. Counts must agree, preserving 6,578 current plus three wrappers
for this frozen source if genuine collection succeeds. Selection by display/hash
is prohibited: output is a nonexecutable whole-file recommendation, never a pytest
selector list. Pass/capacity qualification stays false. No shard execution API,
workflow modification or timeout increase is introduced.

## Required Qualification Before A Third Actual Collection

Preserve the 56 current regressions, adapting fixture schemas with unchanged
assertions. Add bounded synthetic tests for:

1. A genuine tiny Git collect-only fixture with an over-8MiB parameter ID: test
   body/fixture sentinel never executes; compact manifest stays small; exact_text
   is null; byte length/digest/display and file mapping match actual collected ID.
2. Actual synthetic JUnit mapping of that oversized ID, mixed with short class
   cases and punctuation/Unicode parameters; exact exhaustive candidate coverage.
3. Same long prefix/display and same length but different last byte stay distinct;
   swapped name digest, altered length, inconsistent same-digest lengths, duplicate
   refs, missing/extra XML cases and wrong classname reject.
4. Exact 16KiB versus 16KiB+1 UTF-8 boundaries, multibyte display boundary and short
   exact_text tampering; V1 envelopes are not accepted as V2.
5. Existing historic-provenance substitution, root totals, CLI/config/PYTEST_ADDOPTS,
   strict-markers normalization, nonexecution and no-deselection protections.

Run focused tests, whole Ruff, bare mypy, standalone plugin mypy and diff checks;
freeze for independent review. Only then may root authorize a fresh third log/exit
and genuine frozen collection, followed by an honest terminal-bound N3 candidate.
Preserve both prior failures. No real candidate or capacity estimate exists yet.

## Separate Future Test Artifact Improvement — Not Part Of This Package

Current source candidates are `tests/test_campaign_review.py`'s
`test_reject_unvalidated_media` data parametrization and
`tests/test_omnisend_http_runtime.py`'s
`test_omnisend_invalid_problem_preserves_header` body parametrization. Explicit IDs
such as `svg`, `non_image`, `empty`, `over_limit`, and `invalid_json`, `non_object`,
`oversized_problem` would avoid embedding input bytes in future node/XML names.
Keep all byte values, sizes, backend parametrization, assertions and counts intact.

That is a separate coordinated consumer-test change: it changes future node IDs,
requires appropriate focused compatibility evidence and a new collection, and must
not rewrite the frozen W1 XML or manifests. Do not edit these files before root
coordinates the concurrent historical fixture work. Compact V2 must still handle
original W1 IDs honestly; renamed future IDs cannot repair their provenance.
