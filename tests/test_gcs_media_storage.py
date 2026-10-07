"""Offline SDK contract tests: no credentials, sockets, or bucket configuration."""

import hashlib
from unittest.mock import MagicMock, create_autospec

import pytest
from app.campaign_review.gcs_storage import GCSMediaStore
from app.campaign_review.storage import get_media_store
from app.settings import settings
from fastapi import HTTPException
from google.api_core.exceptions import PreconditionFailed
from google.cloud import storage

DATA = b"private media fixture"
SHA = hashlib.sha256(DATA).hexdigest()


def fixture_store() -> tuple[GCSMediaStore, MagicMock, MagicMock, MagicMock]:
    client = create_autospec(storage.Client, instance=True)
    bucket = create_autospec(storage.Bucket, instance=True)
    blob = create_autospec(storage.Blob, instance=True)
    client.get_bucket.return_value = bucket
    bucket.iam_configuration.uniform_bucket_level_access_enabled = True
    bucket.iam_configuration.public_access_prevention = "enforced"
    bucket.blob.return_value = blob
    blob.generation = 42
    blob.size = len(DATA)
    blob.download_to_file.side_effect = lambda target, **kwargs: target.write(DATA)
    return GCSMediaStore("inlet-private-fixture", client), client, bucket, blob


@pytest.mark.parametrize("race", [False, True])
def test_immutable_upload_verifies_winner_and_pins_download(race: bool) -> None:
    store, client, bucket, blob = fixture_store()
    if race:
        blob.upload_from_file.side_effect = PreconditionFailed("fixture race")  # type: ignore[no-untyped-call]
    store.put_if_absent(1, SHA, len(DATA), [DATA])
    kwargs = blob.upload_from_file.call_args.kwargs
    assert kwargs == dict(
        size=len(DATA),
        content_type="application/octet-stream",
        if_generation_match=0,
        checksum=None,
        timeout=30,
        retry=None,
    )
    assert blob.download_to_file.call_args.kwargs == dict(
        start=0,
        end=len(DATA),
        raw_download=True,
        if_generation_match=42,
        timeout=30,
        retry=None,
        checksum="crc32c",
    )
    client.get_bucket.assert_called_with("inlet-private-fixture", timeout=15, retry=None)
    assert client.get_bucket.call_count == 3
    bucket.blob.assert_called_with(f"inlet/media/v1/workspaces/1/{SHA}", generation=42)
    blob.delete.assert_not_called()
    bucket.patch.assert_not_called()


@pytest.mark.parametrize("uniform,pap", [(False, "enforced"), (True, "inherited"), (True, None)])
def test_actual_private_policy_required(uniform: bool, pap: str | None) -> None:
    store, _, bucket, blob = fixture_store()
    bucket.iam_configuration.uniform_bucket_level_access_enabled = uniform
    bucket.iam_configuration.public_access_prevention = pap
    with pytest.raises(OSError, match="private media write unavailable"):
        store.put_if_absent(1, SHA, len(DATA), [DATA])
    with pytest.raises(OSError, match="private media read unavailable"):
        store.read_exact(1, SHA, len(DATA))
    blob.upload_from_file.assert_not_called()
    blob.download_to_file.assert_not_called()


@pytest.mark.parametrize("data", [DATA + b"overflow", b"short", b"x" * len(DATA)])
def test_download_bound_and_digest(data: bytes) -> None:
    store, _, _, blob = fixture_store()
    blob.download_to_file.side_effect = lambda target, **kwargs: target.write(data)
    with pytest.raises(OSError):
        store.read_exact(1, SHA, len(DATA))


@pytest.mark.parametrize(
    "generation,size", [(None, len(DATA)), (0, len(DATA)), (42, len(DATA) + 1)]
)
def test_metadata_rejected_before_download(generation: int | None, size: int) -> None:
    store, _, _, blob = fixture_store()
    blob.generation, blob.size = generation, size
    with pytest.raises(OSError):
        store.read_exact(1, SHA, len(DATA))
    blob.download_to_file.assert_not_called()


def test_generation_race_fails_closed_without_unpinned_retry() -> None:
    store, _, _, blob = fixture_store()
    blob.download_to_file.side_effect = PreconditionFailed("object changed")  # type: ignore[no-untyped-call]
    with pytest.raises(OSError):
        store.read_exact(1, SHA, len(DATA))
    assert blob.download_to_file.call_count == 1


def test_policy_change_during_read_fails_closed() -> None:
    store, _, bucket, blob = fixture_store()

    def changed(target: object, **kwargs: object) -> None:
        target.write(DATA)  # type: ignore[attr-defined]
        bucket.iam_configuration.public_access_prevention = "inherited"

    blob.download_to_file.side_effect = changed
    with pytest.raises(OSError):
        store.read_exact(1, SHA, len(DATA))


@pytest.mark.parametrize("chunks", [[b"wrong"], [DATA + b"extra"], [b"x" * (1024 * 1024 + 1)]])
def test_invalid_input_never_calls_provider(chunks: list[bytes]) -> None:
    store, client, _, _ = fixture_store()
    with pytest.raises(ValueError):
        store.put_if_absent(1, SHA, len(DATA), chunks)
    client.get_bucket.assert_not_called()


def test_workspace_namespace_and_provider_error_sanitization() -> None:
    store, _, bucket, blob = fixture_store()
    store.read_exact(1, SHA, len(DATA))
    store.read_exact(2, SHA, len(DATA))
    assert bucket.blob.call_args_list[0].args != bucket.blob.call_args_list[2].args
    blob.upload_from_file.side_effect = RuntimeError("secret provider payload")
    with pytest.raises(OSError, match="^private media write unavailable$"):
        store.put_if_absent(1, SHA, len(DATA), [DATA])


@pytest.mark.parametrize("bucket", ["https://evil.example", "a/b", "a.b", "", "../bucket"])
def test_bucket_names_reject_urls_and_paths(bucket: str) -> None:
    with pytest.raises(ValueError):
        GCSMediaStore(bucket, MagicMock())


def test_factory_disabled_without_sdk_client(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock(side_effect=AssertionError("must not discover credentials"))
    monkeypatch.setattr(storage, "Client", client)
    monkeypatch.setattr(settings, "media_storage_mode", "disabled")
    with pytest.raises(HTTPException) as error:
        get_media_store()
    assert error.value.status_code == 503
    client.assert_not_called()


def test_explicit_gcs_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    monkeypatch.setattr(storage, "Client", lambda **kwargs: client)
    monkeypatch.setattr(settings, "media_storage_mode", "gcs")
    monkeypatch.setattr(settings, "media_gcs_bucket", "inlet-private-fixture")
    assert isinstance(get_media_store(), GCSMediaStore)
    client.get_bucket.assert_not_called()


def test_real_sdk_http_generation_and_range_contract() -> None:
    import json

    from google.auth.credentials import AnonymousCredentials
    from requests import Response

    transport = MagicMock()
    metadata = {
        "name": "inlet-private-fixture",
        "iamConfiguration": {
            "uniformBucketLevelAccess": {"enabled": True},
            "publicAccessPrevention": "enforced",
        },
    }

    def response(payload: bytes, content_type: str = "application/json") -> Response:
        result = Response()
        result.status_code = 200
        result._content = payload
        result.raw = MagicMock()
        result.raw.stream.return_value = [payload]
        result.headers["Content-Type"] = content_type
        return result

    transport.request.side_effect = [
        response(json.dumps(metadata).encode()),
        response(
            json.dumps(
                {
                    "generation": "42",
                    "size": str(len(DATA)),
                    "mediaLink": "https://untrusted.invalid/never-follow",
                }
            ).encode()
        ),
        response(DATA, "application/octet-stream"),
        response(json.dumps(metadata).encode()),
    ]
    client = storage.Client(
        project="offline-fixture",
        client_options={"api_endpoint": "https://storage.googleapis.com"},
        credentials=AnonymousCredentials(),  # type: ignore[no-untyped-call]
        _http=transport,
    )
    store = GCSMediaStore("inlet-private-fixture", client)
    assert store.read_exact(1, SHA, len(DATA)) == DATA
    download = transport.request.call_args_list[2]
    url = download.args[1]
    assert url.startswith("https://storage.googleapis.com/")
    assert "ifGenerationMatch=42" in url
    assert download.kwargs["headers"]["range"] == f"bytes=0-{len(DATA)}"


def test_emulator_is_not_runtime_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    monkeypatch.setattr(storage, "Client", client)
    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://untrusted.invalid")
    monkeypatch.setattr(settings, "media_storage_mode", "gcs")
    monkeypatch.setattr(settings, "media_gcs_bucket", "inlet-private-fixture")
    with pytest.raises(HTTPException):
        get_media_store()
    client.assert_not_called()


@pytest.mark.parametrize("wid,sha,size", [(0, SHA, len(DATA)), (True, SHA, len(DATA)),
                                         (1, "../object", len(DATA)), (1, SHA, 0),
                                         (1, SHA, 64 * 1024 * 1024 + 1)])
def test_invalid_scope_has_no_provider_calls(wid: int, sha: str, size: int) -> None:
    store, client, _, _ = fixture_store()
    with pytest.raises(ValueError):
        store.read_exact(wid, sha, size)
    client.get_bucket.assert_not_called()


def test_bucket_metadata_failure_does_not_fall_back() -> None:
    store, client, _, blob = fixture_store()
    client.get_bucket.side_effect = RuntimeError("private provider details")
    with pytest.raises(OSError, match="^private media write unavailable$"):
        store.put_if_absent(1, SHA, len(DATA), [DATA])
    blob.upload_from_file.assert_not_called()


def test_race_winner_with_wrong_content_is_not_accepted_or_overwritten() -> None:
    store, _, _, blob = fixture_store()
    blob.upload_from_file.side_effect = PreconditionFailed("race")  # type: ignore[no-untyped-call]
    blob.download_to_file.side_effect = lambda target, **kwargs: target.write(b"x" * len(DATA))
    with pytest.raises(OSError):
        store.put_if_absent(1, SHA, len(DATA), [DATA])
    assert blob.upload_from_file.call_count == 1
    blob.delete.assert_not_called()


def test_concurrent_same_key_create_has_one_winner() -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock

    store, _, _, blob = fixture_store()
    barrier, lock = Barrier(2), Lock()
    writes = 0

    def upload(*args: object, **kwargs: object) -> None:
        nonlocal writes
        barrier.wait(timeout=5)
        with lock:
            if writes:
                raise PreconditionFailed("race")  # type: ignore[no-untyped-call]
            writes += 1

    blob.upload_from_file.side_effect = upload
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(store.put_if_absent, 1, SHA, len(DATA), [DATA]) for _ in range(2)]
        for job in jobs:
            job.result(timeout=10)
    assert writes == 1
    assert blob.upload_from_file.call_count == 2
    assert blob.download_to_file.call_count == 2


def test_lost_upload_response_can_retry_existing_object() -> None:
    store, _, _, blob = fixture_store()
    blob.upload_from_file.side_effect = [
        TimeoutError("commit outcome unknown"),
        PreconditionFailed("existing object"),  # type: ignore[no-untyped-call]
    ]
    with pytest.raises(OSError):
        store.put_if_absent(1, SHA, len(DATA), [DATA])
    store.put_if_absent(1, SHA, len(DATA), [DATA])
    assert blob.download_to_file.call_count == 1
    blob.delete.assert_not_called()
