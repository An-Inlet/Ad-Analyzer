"""Real synthetic videos and bounded subprocess controls; no advertising providers."""

import hashlib
import os
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from app.ads.enums import AdvertisingPlatform
from app.ads.models import AdvertisingAccount
from app.campaign_review import service, video
from app.campaign_review.contracts import MAX_IMAGE_BYTES, MAX_VIDEO_BYTES, RevisionInput
from app.campaign_review.storage import LocalMediaStore
from app.mandates import service as mandates
from app.mandates.schemas import AccountScope
from app.settings import Settings
from app.sources.models import SourceConnection
from app.workspaces.models import WorkspaceIntegration
from fastapi import HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_campaign_review import png
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_google_action_plans import setup
from tests.test_shopify_sales import configuration as configuration


@pytest.fixture()
def encoded(tmp_path: Path) -> Any:
    if os.name != "posix":
        pytest.skip("bounded decoder requires POSIX")
    if not all(shutil.which(tool) for tool in ("ffmpeg", "ffprobe")):
        if os.environ.get("CI") == "true":
            pytest.fail("CI requires FFmpeg/FFprobe")
        pytest.skip("local video decoder tools unavailable")

    def make(
        *,
        codec: str = "libx264",
        size: str = "64x64",
        rate: int = 10,
        duration: str = "0.5",
        audio: str | None = None,
    ) -> bytes:
        path = tmp_path / (uuid4().hex + ".mp4")
        args = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=green:s={size}:r={rate}"]
        if audio:
            args += ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-c:a", audio]
        args += [
            "-t",
            duration,
            "-c:v",
            codec,
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-y",
            str(path),
        ]
        subprocess.run(args, check=True, capture_output=True, timeout=30)
        return path.read_bytes()

    return make


@pytest.mark.parametrize("audio", [None, "aac"])
def test_real_mp4_full_decode(encoded: Any, audio: str | None) -> None:
    data = encoded(audio=audio)
    info = video.validate_video(data)
    assert (info.width, info.height, info.frame_count) == (64, 64, 5)
    assert 500 <= info.duration_ms <= 550
    assert service.inspect_media(data) == ("video/mp4", 64, 64)


@pytest.mark.parametrize(
    "options",
    [
        {"codec": "mpeg4"},
        {"audio": "libmp3lame"},
        {"size": "1922x2"},
        {"size": "1920x1920"},
        {"rate": 61},
        {"duration": "61", "rate": 1},
    ],
)
def test_real_unsupported_video_rejected(encoded: Any, options: dict[str, Any]) -> None:
    with pytest.raises(video.VideoInvalid):
        video.validate_video(encoded(**options))


def test_truncated_and_corrupt_video_rejected(encoded: Any) -> None:
    data = encoded()
    with pytest.raises(video.VideoInvalid):
        video.validate_video(data[:-30])
    damaged = bytearray(data)
    position = data.index(b"mdat") + 4
    damaged[position:] = b"\0" * (len(data) - position)
    with pytest.raises(video.VideoInvalid):
        video.validate_video(bytes(damaged))


def test_bounds_and_missing_decoder_fail_closed(
    encoded: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(video.VideoInvalid):
        video.validate_video(b"\0" * (MAX_VIDEO_BYTES + 1))
    with pytest.raises(HTTPException) as image:
        service.inspect_media(png() + b"\0" * MAX_IMAGE_BYTES)
    assert image.value.status_code == 413
    data = encoded()
    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    with pytest.raises(HTTPException) as unavailable:
        service.inspect_media(data)
    assert unavailable.value.status_code == 503


@pytest.mark.parametrize("failure", ["time", "output"])
def test_decoder_limits_kill_and_reap_process(
    encoded: Any, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    data = encoded()
    real = subprocess.Popen
    children = []

    def replacement(args: Any, **kwargs: Any) -> Any:
        assert "preexec_fn" not in kwargs and kwargs["start_new_session"] is True
        assert "fixture-secret" not in str(kwargs["env"])
        script = (
            "import time; time.sleep(10)"
            if failure == "time"
            else "import sys; sys.stdout.buffer.write(b'x'*65536); sys.stdout.flush()"
        )
        child = real([sys.executable, "-I", "-c", script], **kwargs)
        children.append(child)
        return child

    monkeypatch.setenv("INLET_SYNTHETIC_SECRET", "fixture-secret")
    monkeypatch.setattr(subprocess, "Popen", replacement)
    monkeypatch.setattr(video, "WALL_SECONDS", 0.1 if failure == "time" else 3)
    monkeypatch.setattr(video, "OUTPUT_BYTES", 1024)
    with pytest.raises(video.VideoInvalid):
        video.decoder("probe", data)
    assert children and all(child.poll() is not None for child in children)


def test_tiktok_video_review_is_real_and_publication_stays_disabled(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    encoded: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalMediaStore(tmp_path / "private")
    with Session(customer_engine) as db:
        mandate, _, _ = setup(db, configuration)
        integration = WorkspaceIntegration(
            workspace_id=mandate.workspace_id,
            integration_key="video-review",
            provider="tiktok_ads",
            display_name="Fixture TikTok",
            status="active",
            configuration={},
        )
        db.add(integration)
        db.flush()
        account = AdvertisingAccount(
            workspace_id=mandate.workspace_id,
            connection_id=integration.id,
            platform=AdvertisingPlatform.TIKTOK_ADS,
            external_account_id="123",
            name="Fixture TikTok",
            currency_code="USD",
            time_zone="UTC",
        )
        db.add(account)
        db.flush()
        db.add(
            SourceConnection(
                id=uuid4().hex,
                workspace_id=mandate.workspace_id,
                integration_id=integration.id,
                account_id=account.id,
                provider="tiktok_ads",
                external_id="123",
                status="connected",
                generation=1,
                window_start=NOW.date(),
                window_end=NOW.date(),
                staged={},
            )
        )
        policy = mandates.policy(db, mandate)
        policy.accounts = [
            AccountScope(platform="tiktok_ads", connection_id=integration.id, account_id=account.id)
        ]
        mandates.edit(db, mandate, mandate.revision, policy, "owner", NOW)
        mandates.approve(db, mandate, mandate.revision, "owner", NOW)
        db.commit()
        data = encoded()
        uploaded = service.upload(db, mandate.workspace_id, "owner", data, store, NOW)
        assert uploaded.mime == "video/mp4" and uploaded.sha256 == hashlib.sha256(data).hexdigest()
        body = RevisionInput(
            account=policy.accounts[0],
            mandate_id=mandate.id,
            mandate_revision=mandate.revision,
            currency="USD",
            budget_micros=60,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=1),
            content={
                "kind": "tiktok_website_conversion_video_v1",
                "objective": "website_conversion",
                "name": "Synthetic video",
                "landing_page": "https://example.invalid/shop",
                "audience": {"countries": ["US"], "languages": ["en"]},
                "text": "Supplied text",
                "call_to_action": "SHOP_NOW",
                "media": {"media_id": uploaded.id, "sha256": uploaded.sha256},
            },
        )
        row = service.revise(db, mandate.workspace_id, body, "owner", store, NOW)
        _, artifact = service.preview(db, mandate.workspace_id, row.draft_id, store, NOW)
        assert artifact.offline_reviewable and not artifact.publication_eligible
        assert "provider_publication_disabled" in artifact.publication_blockers
        service.approve(db, mandate.workspace_id, row.draft_id, 1, row.digest, "owner", store, NOW)
        image = service.upload(db, mandate.workspace_id, "owner", png(), store, NOW)
        bad = body.model_dump(mode="json")
        bad["content"]["media"] = {"media_id": image.id, "sha256": image.sha256}
        with pytest.raises(HTTPException) as wrong:
            service.revise(
                db, mandate.workspace_id, RevisionInput.model_validate(bad), "owner", store, NOW
            )
        assert wrong.value.status_code == 422
        # Isolate the inverse MIME policy after binding (the Meta integration path
        # itself is covered by test_campaign_review's real Meta review journey).
        from app.campaign_review.models import CampaignDraft

        bad["content"].update(
            kind="meta_website_sales_image_v1", objective="website_sales", headline="Shop"
        )
        bad["content"]["media"] = {"media_id": uploaded.id, "sha256": uploaded.sha256}
        bad["account"]["platform"] = "meta_ads"
        monkeypatch.setattr(service, "binding", lambda *a: 1)
        with pytest.raises(HTTPException) as inverse:
            service.artifact(
                db,
                CampaignDraft(id=uuid4().hex, workspace_id=mandate.workspace_id, revision=1),
                RevisionInput.model_validate(bad),
                store,
                NOW,
            )
        assert inverse.value.status_code == 422


def test_decoder_start_failure_unavailable(encoded: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    data = encoded()

    def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise OSError("private deployment detail")

    monkeypatch.setattr(subprocess, "Popen", unavailable)
    with pytest.raises(video.VideoUnavailable, match="^video validation unavailable$"):
        video.decoder("probe", data)


@pytest.mark.skipif(os.name != "posix", reason="POSIX resource worker")
@pytest.mark.parametrize("mode", ["probe", "decode"])
def test_worker_fixed_protocol_and_resource_limits(
    mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import resource

    from app.campaign_review import video_worker

    limits = []
    calls = []
    monkeypatch.setattr(sys, "argv", ["worker", mode])
    monkeypatch.setattr(resource, "setrlimit", lambda kind, value: limits.append((kind, value)))
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(os, "execv", lambda tool, args: calls.append(args))
    video_worker.main()
    args = calls[0]
    assert args[args.index("-protocol_whitelist") + 1] == "pipe"
    assert args[args.index("-enable_drefs") + 1] == "0"
    assert args[args.index("-use_absolute_path") + 1] == "0"
    assert "pipe:0" in args and not any("http" in x or "file:" in x for x in args)
    assert len(limits) == 5
    assert (resource.RLIMIT_CPU, (18, 20)) in limits
    assert (resource.RLIMIT_FSIZE, (0, 0)) in limits
