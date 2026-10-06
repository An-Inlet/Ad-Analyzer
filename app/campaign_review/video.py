"""Bounded byte-only MP4 validation; these controls are not an OS security sandbox."""

import json
import os
import selectors
import shutil
import signal
import subprocess
import sys
import time
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.campaign_review.contracts import MAX_VIDEO_BYTES

WALL_SECONDS = 22.0
OUTPUT_BYTES = 2 * 1024 * 1024
ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "OMP_NUM_THREADS": "1"}


class VideoInvalid(ValueError):
    pass


class VideoUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration_ms: int
    frame_count: int


def decoder(mode: str, data: bytes) -> bytes:
    if os.name != "posix" or not all(
        shutil.which(x, path=ENV["PATH"]) for x in ("ffmpeg", "ffprobe")
    ):
        raise VideoUnavailable("video validation unavailable")
    worker = str(Path(__file__).with_name("video_worker.py"))
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", worker, mode],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=ENV,
            start_new_session=True,
        )
    except OSError:
        raise VideoUnavailable("video validation unavailable") from None
    deadline = time.monotonic() + WALL_SECONDS
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    offset = 0
    try:
        with selectors.DefaultSelector() as selector:
            assert (
                process.stdin is not None
                and process.stdout is not None
                and process.stderr is not None
            )
            for name, file, event in [
                ("stdin", process.stdin, selectors.EVENT_WRITE),
                ("stdout", process.stdout, selectors.EVENT_READ),
                ("stderr", process.stderr, selectors.EVENT_READ),
            ]:
                os.set_blocking(file.fileno(), False)
                selector.register(file, event, name)
            while selector.get_map():
                if time.monotonic() >= deadline:
                    raise VideoInvalid("video validation resource limit")
                for key, _ in selector.select(min(0.1, max(0, deadline - time.monotonic()))):
                    if key.data == "stdin":
                        try:
                            offset += os.write(key.fd, memoryview(data)[offset : offset + 65536])
                        except BrokenPipeError:
                            offset = len(data)
                        if offset == len(data):
                            selector.unregister(key.fileobj)
                            process.stdin.close()
                    else:
                        chunk = os.read(key.fd, 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        buffers[key.data].extend(chunk)
                        limit = 65536 if key.data == "stderr" else OUTPUT_BYTES
                        if len(buffers[key.data]) > limit:
                            raise VideoInvalid("video validation output limit")
            code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
            if code == 78:
                raise VideoUnavailable("video validation unavailable")
            if code != 0 or buffers["stderr"]:
                raise VideoInvalid("invalid bounded MP4 video")
        return bytes(buffers["stdout"])
    except (OSError, subprocess.TimeoutExpired):
        raise VideoInvalid("video validation failed") from None
    finally:
        if process.poll() is None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


def container(data: bytes) -> None:
    if not 0 < len(data) <= MAX_VIDEO_BYTES or data[4:8] != b"ftyp":
        raise VideoInvalid("bounded MP4 required")
    if data[8:12] not in {b"isom", b"iso2", b"iso5", b"iso6", b"mp41", b"mp42", b"avc1"}:
        raise VideoInvalid("MP4 brand unavailable")
    offset, boxes = 0, set()
    while offset < len(data):
        if len(data) - offset < 8:
            raise VideoInvalid("truncated MP4")
        size = int.from_bytes(data[offset : offset + 4], "big")
        kind = data[offset + 4 : offset + 8]
        header = 8
        if size == 1:
            header = 16
            if len(data) - offset < header:
                raise VideoInvalid("truncated MP4")
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
        if size < header or offset + size > len(data):
            raise VideoInvalid("truncated or unbounded MP4")
        boxes.add(kind)
        offset += size
    if not {b"ftyp", b"moov", b"mdat"} <= boxes:
        raise VideoInvalid("complete MP4 required")


def number(value: Any) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError()
    return result


def validate_video(data: bytes) -> VideoInfo:
    container(data)
    try:
        probe = json.loads(decoder("probe", data))
        streams = probe["streams"]
        videos = [s for s in streams if s["codec_type"] == "video"]
        audio = [s for s in streams if s["codec_type"] == "audio"]
        if len(videos) != 1 or len(audio) > 1 or len(streams) != len(videos) + len(audio):
            raise ValueError()
        video = videos[0]
        if video["codec_name"] != "h264" or any(s["codec_name"] != "aac" for s in audio):
            raise ValueError()
        width, height = int(video["width"]), int(video["height"])
        fps = Fraction(video["avg_frame_rate"])
        duration = number(probe["format"]["duration"])
        video_duration = number(video["duration"])
        if not (
            1 <= width <= 1920
            and 1 <= height <= 1920
            and width * height <= 2073600
            and 0 < fps <= 60
            and 0 < duration <= 60
            and 0 < video_duration <= 60
        ):
            raise ValueError()
        frames = [f for f in probe["frames"] if f["media_type"] == "video"]
        if not 1 <= len(frames) <= 3600 or len(frames) != int(video["nb_frames"]):
            raise ValueError()
        times = []
        for frame in frames:
            if (frame["width"], frame["height"]) != (width, height):
                raise ValueError()
            times.append(number(frame["best_effort_timestamp_time"]))
        if (
            times[0] < 0
            or times[-1] > 60
            or any(
                b - a < Decimal(1) / 60 - Decimal("0.000001")
                for a, b in zip(times, times[1:], strict=False)
            )
        ):
            raise ValueError()
        # Permit one frame of codec timestamp rounding, never extra duration/frames.
        tolerance = min(Decimal(fps.denominator) / fps.numerator, Decimal("0.05")) + Decimal(
            "0.000001"
        )
        if (
            abs(video_duration - (times[-1] - times[0] + Decimal(fps.denominator) / fps.numerator))
            > tolerance
        ):
            raise ValueError()
        progress = decoder("decode", data).decode("ascii")
        fields = dict(line.split("=", 1) for line in progress.splitlines() if "=" in line)
        if fields.get("progress") != "end" or int(fields.get("frame", "0")) != len(frames):
            raise ValueError()
        elapsed = number(fields["out_time_us"]) / 1000000
        if elapsed < 0 or abs(elapsed - duration) > tolerance or elapsed > Decimal("60.000001"):
            raise ValueError()
        return VideoInfo(width, height, int(duration * 1000), len(frames))
    except VideoUnavailable:
        raise
    except (KeyError, TypeError, ValueError, InvalidOperation, ZeroDivisionError):
        raise VideoInvalid("valid bounded H264 MP4 with optional AAC required") from None
