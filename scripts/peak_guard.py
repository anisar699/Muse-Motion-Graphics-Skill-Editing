#!/usr/bin/env python3
"""Muse Motion peak guard (v1.3).

Why this exists: loudnorm's linear pass targets the true-peak ceiling on the
PCM it is given, but the final AAC encode can overshoot it (measured on real
deliveries: a master normalised to TP -1.0 came back from the encoder at
-0.95 and -0.7 dBTP, failing the QC gate). This script closes that loop:
measure the ENCODED file, and if its true peak is above the ceiling, apply
the smallest sufficient gain reduction as an audio-only remux (video is
stream-copied, never re-encoded) and measure again.

Usage:
  python3 peak_guard.py FILE [--ceiling -1.0] [--margin 0.3]
                        [--in-place] [--report report.json]

Exit codes: 0 = peak within ceiling (already, or fixed), 1 = still above
ceiling after the fix attempt, 2 = tool error (missing file, no audio,
ffmpeg failure). The input file is never modified unless --in-place is
given; otherwise the fixed copy is written next to it as
<name>-peakfixed<ext>.
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path


def measure_tp(path):
    """True peak (dBTP) via ffmpeg's loudnorm measurement pass."""
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-i", str(path), "-vn", "-af",
         "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr[-500:]
    try:
        block = r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1]
        m = json.loads(block)
        return float(m["input_tp"]), None
    except Exception as e:  # noqa: BLE001
        return None, f"could not parse loudnorm output: {e}"


def has_audio(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--ceiling", type=float, default=-1.0)
    ap.add_argument("--margin", type=float, default=0.3,
                    help="extra dB of headroom added to the fix (default 0.3)")
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument("--report")
    args = ap.parse_args()

    src = Path(args.file)
    result = {"file": str(src), "ceiling": args.ceiling, "margin": args.margin}

    def finish(code, status):
        result["status"] = status
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=1))
        print(f"peak_guard: {status} "
              f"(before={result.get('tp_before')} after={result.get('tp_after')})")
        sys.exit(code)

    if not src.is_file():
        print(f"peak_guard: ERROR file not found: {src}", file=sys.stderr)
        result["status"] = "error_no_file"
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=1))
        sys.exit(2)
    if not has_audio(src):
        print("peak_guard: ERROR no audio stream", file=sys.stderr)
        result["status"] = "error_no_audio"
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=1))
        sys.exit(2)

    tp, err = measure_tp(src)
    if tp is None:
        print(f"peak_guard: ERROR measurement failed: {err}", file=sys.stderr)
        result["status"] = "error_measure"
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=1))
        sys.exit(2)
    result["tp_before"] = round(tp, 2)

    if tp <= args.ceiling:
        result["tp_after"] = result["tp_before"]
        finish(0, "pass_already_within_ceiling")

    reduction = tp - args.ceiling + args.margin
    reduction = math.ceil(reduction * 10) / 10  # round up to 0.1 dB steps
    result["reduction_db"] = reduction
    out = src if args.in_place else src.with_name(src.stem + "-peakfixed" + src.suffix)
    tmp = src.with_name(src.stem + "-peakfix-tmp" + src.suffix)
    r = subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(src),
         "-c:v", "copy", "-af", f"volume=-{reduction:.1f}dB",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)],
        capture_output=True, text=True)
    if r.returncode != 0:
        print(f"peak_guard: ERROR remux failed: {r.stderr[-500:]}", file=sys.stderr)
        result["status"] = "error_remux"
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=1))
        sys.exit(2)
    tp2, err = measure_tp(tmp)
    if tp2 is None:
        tmp.unlink(missing_ok=True)
        print(f"peak_guard: ERROR re-measurement failed: {err}", file=sys.stderr)
        result["status"] = "error_measure_after"
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=1))
        sys.exit(2)
    result["tp_after"] = round(tp2, 2)
    if tp2 <= args.ceiling:
        tmp.replace(out)
        result["output"] = str(out)
        finish(0, "fixed")
    tmp.unlink(missing_ok=True)
    finish(1, "still_above_ceiling")


if __name__ == "__main__":
    main()
