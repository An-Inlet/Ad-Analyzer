"""Standalone POSIX resource limiter; exec fixed decoder commands without server fork hooks."""

import os
import resource
import shutil
import sys


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"probe", "decode"}:
        raise SystemExit(78)
    resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (18, 20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    mode = sys.argv[1]
    tool = shutil.which("ffprobe" if mode == "probe" else "ffmpeg")
    if not tool:
        raise SystemExit(78)
    common = [
        "-v",
        "error",
        "-max_alloc",
        "67108864",
        "-protocol_whitelist",
        "pipe",
        "-format_whitelist",
        "mov",
        "-codec_whitelist",
        "h264,aac",
        "-enable_drefs",
        "0",
        "-use_absolute_path",
        "0",
        "-threads",
        "1",
    ]
    if mode == "probe":
        args = [
            tool,
            *common,
            "-f",
            "mov",
            "-show_frames",
            "-show_entries",
            "format=format_name,duration:stream=index,codec_name,codec_type,width,height,"
            "avg_frame_rate,duration,nb_frames:"
            "frame=media_type,width,height,best_effort_timestamp_time,pkt_duration_time",
            "-of",
            "json",
            "pipe:0",
        ]
    else:
        args = [
            tool,
            *common,
            "-nostdin",
            "-xerror",
            "-err_detect",
            "explode",
            "-f",
            "mov",
            "-i",
            "pipe:0",
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-sn",
            "-dn",
            "-threads",
            "1",
            "-filter_threads",
            "1",
            "-filter_complex_threads",
            "1",
            "-progress",
            "pipe:1",
            "-nostats",
            "-f",
            "null",
            "pipe:1",
        ]
    os.execv(tool, args)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError):
        raise SystemExit(78) from None
