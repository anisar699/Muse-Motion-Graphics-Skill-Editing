#!/usr/bin/env python3
"""Muse Motion caption checker (v1.3) - the automatable part of AUD-27.

Checks an SRT caption file against the skill's caption limits:
  - line length      (default max 42 chars per line)
  - line count       (default max 2 lines per cue; v1.7, audit M-05)
  - reading speed    (default max 20 chars/second over the cue duration)
  - cue duration     (warns below 0.7s and above 7s by default; a cue
                      ending at or before it starts is an ERROR, v1.7)
  - timing sanity    (overlapping cues are errors; gaps under 0.08s warn)
  - contrast         (only when --fg and --bg colours are given: the WCAG
                      contrast ratio of the caption style must be >= 4.5)

Threshold note (v1.7, audit L-01): the numeric limits match the caption
engine's (42 chars, 20 cps, 0.7s floor). The SEVERITY differs by design:
this checker is the strict gate for sidecar SRT deliverables, so over-speed
is an error here, while build_captions.py declares over-speed cues as
speech-density bursts in captions.json for the burned-in workflow.

What stays manual (honestly): flash-rate judgement for graphic sequences
and whether a caption's wording is right. This tool checks form, not sense.

Usage:
  python3 check_captions.py captions.srt [--max-line 42] [--max-cps 20]
      [--min-dur 0.8] [--max-dur 7] [--fg FFFFFF] [--bg 000000]
      [--report report.json]
Exit codes: 0 = no errors, 1 = errors found, 2 = tool error.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TIME_RE = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{3})")


def to_s(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(text):
    cues = []
    for block in re.split(r"\r?\n\r?\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        tm = None
        body = []
        for ln in lines:
            mm = TIME_RE.search(ln)
            if mm:
                tm = (to_s(*mm.groups()[:4]), to_s(*mm.groups()[4:]))
            elif tm is not None:
                body.append(ln.strip())
            # lines before the timing line (the numeric index) are ignored
        if tm is not None:
            cues.append({"start": tm[0], "end": tm[1], "lines": body})
    return cues


def rel_lum(hexstr):
    h = hexstr.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))

    def f(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(fg, bg):
    l1, l2 = rel_lum(fg), rel_lum(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--max-line", type=int, default=42)
    ap.add_argument("--max-lines", type=int, default=2)
    ap.add_argument("--max-cps", type=float, default=20.0)
    ap.add_argument("--min-dur", type=float, default=0.7)
    ap.add_argument("--max-dur", type=float, default=7.0)
    ap.add_argument("--fg")
    ap.add_argument("--bg")
    ap.add_argument("--report")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.is_file():
        print(f"check_captions: ERROR file not found: {p}", file=sys.stderr)
        sys.exit(2)
    cues = parse_srt(p.read_text(encoding="utf-8", errors="replace"))
    if not cues:
        print("check_captions: ERROR no cues parsed (not an SRT file?)",
              file=sys.stderr)
        sys.exit(2)

    errors, warnings = [], []
    prev_end = None
    for i, c in enumerate(cues, start=1):
        dur = c["end"] - c["start"]
        text = " ".join(c["lines"])
        if len(c["lines"]) > args.max_lines:
            errors.append(f"cue {i}: {len(c['lines'])} lines > {args.max_lines}")
        if dur <= 0:
            errors.append(f"cue {i}: ends at {c['end']:.2f}s at or before it starts "
                          f"at {c['start']:.2f}s (backwards cue)")
        for ln in c["lines"]:
            if len(ln) > args.max_line:
                errors.append(f"cue {i}: line {len(ln)} chars > {args.max_line}: {ln!r}")
        if dur > 0:
            cps = len(text) / dur
            if cps > args.max_cps:
                errors.append(f"cue {i}: reading speed {cps:.1f} cps > {args.max_cps}")
        if dur < args.min_dur:
            warnings.append(f"cue {i}: duration {dur:.2f}s < {args.min_dur}s")
        if dur > args.max_dur:
            warnings.append(f"cue {i}: duration {dur:.2f}s > {args.max_dur}s")
        if prev_end is not None:
            if c["start"] < prev_end:
                errors.append(f"cue {i}: starts at {c['start']:.2f}s before previous cue ends at {prev_end:.2f}s (overlap)")
            elif c["start"] - prev_end < 0.08:
                warnings.append(f"cue {i}: gap to previous cue only {c['start'] - prev_end:.2f}s")
        prev_end = c["end"]

    contrast_info = None
    if args.fg and args.bg:
        try:
            ratio = contrast(args.fg, args.bg)
            contrast_info = {"fg": args.fg, "bg": args.bg, "ratio": round(ratio, 2)}
            if ratio < 4.5:
                errors.append(f"contrast {ratio:.2f}:1 < 4.5:1 (WCAG AA for caption text)")
        except ValueError:
            print("check_captions: ERROR --fg/--bg must be hex colours like FFFFFF",
                  file=sys.stderr)
            sys.exit(2)

    for e in errors:
        print(f"FAIL {e}")
    for w in warnings:
        print(f"WARN {w}")
    verdict = "FAIL" if errors else "PASS"
    print(f"check_captions: {verdict} - {len(cues)} cues, "
          f"{len(errors)} errors, {len(warnings)} warnings")
    if args.report:
        Path(args.report).write_text(json.dumps(
            {"file": str(p), "cues": len(cues), "errors": errors,
             "warnings": warnings, "contrast": contrast_info,
             "verdict": verdict}, indent=1))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
