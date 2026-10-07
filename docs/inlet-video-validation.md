# Inlet Offline Video Validation

B14 accepts actual MP4/H.264 bytes with zero or one AAC audio stream for TikTok
campaign review. Meta image campaigns still require validated static JPEG/PNG.
The upload Content-Type and filename do not establish the media type. Upload,
preview, revision, and approval verify bytes; exact hashes remain bound to the
review. Offline approval never enables provider publication.

Internal acceptance limits (not provider certification): 64 MiB video/media,
8 MiB images, 128 MiB workspace library; video duration at most 60 seconds,
width/height at most 1920, at most 2,073,600 pixels, and at most 60 frames/second.
Only complete, explicitly sized MP4 atoms and supported MP4 brands are accepted.
Non-streamable or unusual MP4 files can fail closed and need re-encoding.

FFprobe decodes every frame; FFmpeg independently performs a complete strict
video/audio decode. Stream codecs, actual frame dimensions, timestamp spacing,
frame count, duration, and terminal decode progress must agree. Timestamp rounding
allows at most one frame capped at 50 ms plus one microsecond; it does not extend
the 60-second media limit (only one microsecond of decoder clock rounding).

Each decoder launches through a standalone isolated Python worker, then execs
fixed arguments. Input is stdin only, protocols are restricted to `pipe`, MOV
external data references and absolute paths are disabled, and only MOV/H.264/AAC
are enabled. The worker inherits a fixed minimal environment, no application
secrets. It sets 1.5 GiB address-space, 18/20 second CPU, zero file-output/core,
and 32-descriptor limits. Parent-side nonblocking pipes bound stdout to 2 MiB,
stderr to 64 KiB, and each invocation to 22 seconds, then kill/reap its process
group. Probe plus decode can take up to 44 seconds. Resource violations are safe
validation failures; unavailable binaries fail closed with an explicit 503.

These measures are **not an OS sandbox or proof against decoder vulnerabilities**.
Production qualification still requires patched FFmpeg, container resource limits,
concurrency/load testing, and review of the deployment's isolation. The Docker
image installs the distribution FFmpeg package; CI requires both binaries. Rebuild
and patch images routinely. Async upload must run the serial authorization/upload
service boundary in a worker thread after bounded body receipt; release integration
coordinates this with the independent review-authorization fix.

Offline evidence uses generated green test clips and disposable PostgreSQL only:
valid silent/AAC clips, wrong video/audio codecs, dimension/pixel/frame-rate/duration
limits, truncated/corrupt data, cross-campaign MIME rejection, missing decoder,
subprocess startup failure, output/time cleanup, fixed protocol/resource controls,
and exact TikTok review/approval with publication still disabled. No customer
media, provider requests, or live publishing were used. Provider encoding acceptance,
production container behavior, and playback on customer browsers remain unverified.

References: [FFmpeg protocol options](https://ffmpeg.org/ffmpeg-protocols.html#Protocol-Options),
[MOV demuxer options](https://ffmpeg.org/ffmpeg-formats.html),
[FFprobe frame inspection](https://ffmpeg.org/ffprobe.html).

## Decoder Clock Compatibility

Ubuntu 24.04 FFmpeg 6.1.1-3ubuntu5 reports the final decoded video frame's start in
null-muxer `out_time_us` for silent clips; FFmpeg 7.1.5 reports its end. The same
five-frame 10 fps MP4 has a validated duration of 0.5 seconds and frame starts
0.0–0.4 seconds, producing progress clocks 0.4 and 0.5 respectively. The validator
accepts the exact final decoded frame-start clock (within one microsecond) only
when there is no audio stream. It does not widen the duration tolerance. Full
FFprobe frame/duration checks, independent terminal FFmpeg decode, matching total
frame count, and the strict 60-second bound remain mandatory. Audio still requires
an end-of-stream clock matching the existing duration tolerance.

Reproduced the original failure and fixed behavior using identical synthetic bytes
in a disposable Ubuntu 24.04 container. Ten actual FFmpeg 6.1 cases passed: silent
and AAC accepted; wrong video/audio codecs, dimensions/pixels/frame rate/duration,
truncation and corruption rejected. Local 7.1 regressions additionally reject
nearby-but-wrong progress clocks and mismatched frame counts/audio timing. No
production media or provider access was involved.
