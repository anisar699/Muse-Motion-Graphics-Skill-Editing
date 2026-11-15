#!/usr/bin/env python3
"""Muse Motion frame sampler v1.2.
Extracts deterministic frames, builds a contact sheet, and writes a manifest.
Visual judgement still requires human sign-off - this script never claims a
visual PASS.

Usage:
  sample_frames.py <video> <output_dir> [--directive directive.json]

Without a directive it samples hook, quarter, hero (midpoint), three-quarter
and end positions. With --directive it also samples every beat start, every
reveal_sync time and every beat end from the directive.
Alpha frames are composited onto a checkerboard instead of black.
Exit codes: 0 frames extracted, 1 extraction failed / no frames, 2 tool error
(bad input, ffprobe/ffmpeg/Pillow unavailable).
Requires: ffmpeg, ffprobe, Pillow (see requirements.txt).
"""
import json, subprocess, sys, pathlib

try:
    from PIL import Image, ImageDraw
except Exception:
    print("TOOL ERROR: Pillow is not installed (see requirements.txt)")
    raise SystemExit(2)


def checkerboard(w, h, cell=16):
    bg = Image.new("RGB", (w, h), (204, 204, 204))
    d = ImageDraw.Draw(bg)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            if (x // cell + y // cell) % 2:
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(140, 140, 140))
    return bg


def flatten(fp):
    im = Image.open(fp)
    if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = checkerboard(im.width, im.height)
        bg.paste(im, (0, 0), im)
        return bg
    return im.convert("RGB")


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    directive_path = None
    if "--directive" in argv:
        i = argv.index("--directive")
        if i + 1 >= len(argv):
            print("TOOL ERROR: --directive needs a path")
            return 2
        directive_path = argv[i + 1]
        args = [a for a in args if a != directive_path]
    unknown = [a for a in argv[1:] if a.startswith("--") and a != "--directive"]
    if unknown:
        print(f"TOOL ERROR: unknown flag {unknown[0]}")
        return 2
    if len(args) != 2:
        print("Usage: sample_frames.py <video> <output_dir> [--directive directive.json]")
        return 2
    src = pathlib.Path(args[0])
    out = pathlib.Path(args[1])
    if not src.is_file():
        print(f"TOOL ERROR: video not found: {src}")
        return 2
    try:
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "json", str(src)], capture_output=True, text=True, timeout=60)
        dur = float(json.loads(probe.stdout)["format"]["duration"])
    except FileNotFoundError:
        print("TOOL ERROR: ffprobe is not available on PATH")
        return 2
    except Exception:
        print(f"ERROR: could not probe a duration from {src} (not a media file?)")
        return 2
    points = {"hook": 0.5, "quarter": dur * 0.25, "hero": dur * 0.5,
              "three_quarter": dur * 0.75, "end": max(0.1, dur - 0.4)}
    if directive_path:
        try:
            d = json.loads(pathlib.Path(directive_path).read_text(encoding="utf-8"))
            for b in d.get("beats") or []:
                bid = b.get("id") or "beat"
                for label, t in (("start", b.get("start")), ("end", b.get("end"))):
                    if isinstance(t, (int, float)):
                        points[f"{bid}_{label}"] = min(max(float(t), 0.0), max(0.0, dur - 0.05))
                for r in b.get("reveal_sync") or []:
                    t = r.get("time")
                    if isinstance(t, (int, float)):
                        points[f"{bid}_reveal_{r.get('element', '')}"] = min(max(float(t), 0.0), max(0.0, dur - 0.05))
        except Exception as exc:
            print(f"TOOL ERROR: could not read directive: {exc}")
            return 2
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for name, t in points.items():
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:60]
        fp = out / f"frame_{safe}_{t:.1f}s.png"
        try:
            r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(src),
                                "-frames:v", "1", str(fp)], capture_output=True, text=True, timeout=120)
        except FileNotFoundError:
            print("TOOL ERROR: ffmpeg is not available on PATH")
            return 2
        if r.returncode == 0 and fp.exists():
            frames.append((name, t, fp))
    if not frames:
        print("ERROR: no frames could be extracted")
        manifest = {"source": str(src), "duration_s": dur, "frames": [],
                    "contact_sheet": None, "human_signoff_required": True}
        (out / "frames_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        return 1
    thumbs = []
    for name, t, fp in frames:
        im = flatten(fp)
        im.thumbnail((360, 640))
        canvas = Image.new("RGB", (im.width, im.height + 28), (10, 10, 10))
        canvas.paste(im, (0, 28))
        ImageDraw.Draw(canvas).text((8, 7), f"{name} @ {t:.1f}s", fill=(255, 255, 255))
        thumbs.append(canvas)
    w = sum(t.width for t in thumbs)
    h = max(t.height for t in thumbs)
    sheet = Image.new("RGB", (w, h), (0, 0, 0))
    x = 0
    for t in thumbs:
        sheet.paste(t, (x, 0))
        x += t.width
    sheet_path = out / "contact_sheet.png"
    sheet.save(sheet_path)
    manifest = {"source": str(src), "duration_s": dur,
                "frames": [{"label": n, "time_s": round(t, 2), "file": str(f)} for n, t, f in frames],
                "contact_sheet": str(sheet_path),
                "human_signoff_required": True}
    (out / "frames_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("frames:", len(frames), "contact sheet:", sheet_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
