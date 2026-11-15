#!/usr/bin/env python3
"""Muse Motion frame sampler (MM-012 partial automation).
Extracts deterministic frames at hook, quarter, hero, three-quarter and end
positions, builds a contact sheet, and writes a manifest. Visual judgement
still requires human sign-off - this script never claims a visual PASS.
Usage: sample_frames.py <video> <output_dir>
"""
import json, subprocess, sys, pathlib
from PIL import Image, ImageDraw

def main():
    if len(sys.argv) != 3:
        print("Usage: sample_frames.py <video> <output_dir>"); return 2
    src = pathlib.Path(sys.argv[1]); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    probe = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(src)],
                           capture_output=True, text=True)
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    points = {"hook": 0.5, "quarter": dur*0.25, "hero": dur*0.5, "three_quarter": dur*0.75, "end": max(0.1, dur-0.4)}
    frames = []
    for name, t in points.items():
        fp = out / f"frame_{name}_{t:.1f}s.png"
        r = subprocess.run(["ffmpeg","-y","-v","error","-ss",f"{t:.2f}","-i",str(src),"-frames:v","1",str(fp)],
                           capture_output=True, text=True)
        if r.returncode == 0 and fp.exists(): frames.append((name, t, fp))
    thumbs = []
    for name, t, fp in frames:
        im = Image.open(fp).convert("RGB"); im.thumbnail((360, 640))
        canvas = Image.new("RGB", (im.width, im.height + 28), (10, 10, 10))
        canvas.paste(im, (0, 28))
        ImageDraw.Draw(canvas).text((8, 7), f"{name} @ {t:.1f}s", fill=(255, 255, 255))
        thumbs.append(canvas)
    if thumbs:
        w = sum(t.width for t in thumbs); h = max(t.height for t in thumbs)
        sheet = Image.new("RGB", (w, h), (0, 0, 0)); x = 0
        for t in thumbs: sheet.paste(t, (x, 0)); x += t.width
        sheet.save(out / "contact_sheet.png")
    manifest = {"source": str(src), "duration_s": dur,
                "frames": [{"label": n, "time_s": round(t, 2), "file": str(f)} for n, t, f in frames],
                "contact_sheet": str(out / "contact_sheet.png"),
                "human_signoff_required": True}
    (out / "frames_manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print("frames:", len(frames), "contact sheet:", out / "contact_sheet.png")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
