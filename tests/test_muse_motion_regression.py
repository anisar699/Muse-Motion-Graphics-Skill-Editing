#!/usr/bin/env python3
"""Muse Motion shipped regression suite (v1.2).

Self-contained: needs python3, ffmpeg, ffprobe and Pillow. Run directly:
  python3 tests/test_muse_motion_regression.py
Exits 0 when every case matches the v1.2 contract, 1 otherwise.
Cases are seeded from the v1.0 auditors' 18-case suite and the v1.1 audit's
reproduction index (section 6), re-expressed against the v1.2 contract.
"""
import copy
import json
import pathlib
import subprocess
import sys
import tempfile

SKILL = pathlib.Path(__file__).resolve().parent.parent
VALIDATOR = SKILL / "scripts" / "validate_directive.py"
QC = SKILL / "scripts" / "qc_probe.py"
SAMPLER = SKILL / "scripts" / "sample_frames.py"
TEMPLATE = SKILL / "templates" / "editorial-directive-template.json"

RESULTS = []


def record(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""))


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def main():
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="mm-tests-"))
    # --- media fixtures ---
    media = tmp / "media10.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30:d=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(media)])
    wav = tmp / "tone.wav"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        "-c:a", "pcm_s16le", str(wav)])
    tpl = json.loads(TEMPLATE.read_text())
    LAY = {"x": 10, "y": 250, "width": 300, "height": 60}

    def base():
        d = copy.deepcopy(tpl)
        d["approval"] = {"status": "approved", "ambiguities": [],
                         "approved_by": "Test", "approved_at": "2026-11-15"}
        d["source"] = {"path": str(media), "duration_s": 10.0}
        d["format"] = {"width": 640, "height": 360, "fps": 30, "aspect": "16:9"}
        d["protected_regions"] = [{"name": "presenter-face", "x": 400, "y": 20,
                                    "width": 200, "height": 200}]
        b = d["beats"][0]
        b.update({"id": "b1", "start": 2.0, "end": 6.0, "role": "hook",
                  "treatment": "SELECTIVE_TEXT", "layout": dict(LAY),
                  "on_screen_copy": [], "reveal_sync": []})
        b.pop("entrance_s", None)
        b.pop("exit_s", None)
        return d

    def vrun(d, *flags):
        p = tmp / "d.json"
        p.write_text(json.dumps(d))
        r = sh(["python3", str(VALIDATOR), str(p), *flags])
        return r.returncode, r.stdout + r.stderr

    rc, _ = vrun(base())
    record("baseline strict directive is VALID", rc == 0)
    d = base(); d["beats"][0].update({"start": 1.0, "end": 1.4})
    record("T01 exact 0.4s hold is VALID (frame compare)", vrun(d)[0] == 0)
    d = base(); d["beats"][0].update({"start": 1.1, "end": 4.1, "treatment": "LOWER_THIRD"})
    record("T02 exact 3.0s LOWER_THIRD is VALID", vrun(d)[0] == 0)
    d = base(); d["beats"][0].update({"layout": {"x": 400, "y": 20, "width": 200, "height": 200},
                                      "allow_protected_overlap": "false"})
    record("T04 string 'false' override does not bypass protection", vrun(d)[0] == 1)
    d = base(); d["beats"][0].update({"layout": {"x": 400, "y": 20, "width": 200, "height": 200},
                                      "allow_protected_overlap": True, "overlap_reason": "deliberate"})
    rc, out = vrun(d)
    record("T05 true override passes WITH a WARN line", rc == 0 and "PROTECTED_OVERRIDE" in out)
    d = base(); d["beats"][0].pop("on_screen_copy")
    d["beats"][0]["reveal_sync"] = [{"element": "NEVER DECLARED", "time": 3.0}]
    record("T06 reveal_sync without on_screen_copy is INVALID", vrun(d)[0] == 1)
    d = base(); d["version"] = True
    record("T09 version true is INVALID", vrun(d)[0] == 1)
    d = base(); d["beats"][0].pop("id")
    record("T10 beat without id is INVALID", vrun(d)[0] == 1)
    d = base(); d["beats"][0]["transtion_in"] = "banana-swirl"
    record("T13 unknown beat key is INVALID", vrun(d)[0] == 1)
    d = base(); d["beats"][0].update({"treatment": "CLEAN_PRESENTER", "layout": "banana"})
    record("T20 non-rect layout is INVALID for any treatment", vrun(d)[0] == 1)
    d = base(); d["beats"][0].update({"start": 1.0, "end": 1.5, "on_screen_copy": ["X" * 500]})
    record("T21 500 chars in 0.5s is INVALID (reading speed)", vrun(d)[0] == 1)
    d = base(); d["format"] = {"width": 1921, "height": 1081, "fps": 1000, "aspect": "16:9"}
    record("T16/T17 odd dims and fps 1000 are INVALID", vrun(d)[0] == 1)
    d = base(); d["format"] = {"width": 1080, "height": 1920, "fps": 30, "aspect": "4:7"}
    record("T22b aspect 4:7 for 1080x1920 is INVALID", vrun(d)[0] == 1)
    d = base(); d["source"] = {"path": str(media), "duration_s": 10.5}
    d["beats"][0].update({"end": 10.5})
    record("T24 declared duration beyond probed is INVALID", vrun(d)[0] == 1)
    d = base(); d["beats"][0]["transition_in"] = "morph"
    record("T14 morph token is VALID", vrun(d)[0] == 0)
    d = base(); d["beats"][0]["transition_in"] = "slide-from-left"
    record("T15 slide-from-left token is VALID", vrun(d)[0] == 0)
    d = base(); d["source"] = {"path": str(wav), "duration_s": 10.0, "kind": "audio"}
    d["beats"][0].update({"treatment": "TITLE"})
    record("T07 audio-kind source is VALID for graphics beats", vrun(d)[0] == 0)
    d = base(); d.pop("source"); d["timeline"] = {"duration_s": 10.0}
    d["beats"][0].update({"treatment": "TITLE"})
    record("T08 graphics-only (kind none) is VALID", vrun(d)[0] == 0)
    r = sh(["python3", str(VALIDATOR), "--drfat", str(tmp / "d.json")])
    record("T18 unknown flag exits 2", r.returncode == 2)
    r = sh(["python3", str(VALIDATOR), str(tmp / "missing.json")])
    record("T19b missing directive file exits 2", r.returncode == 2)

    # --- QC cases ---
    def qrun(target, spec=None):
        p = tmp / "spec.json"
        cmd = ["python3", str(QC), str(target)]
        if spec is not None:
            p.write_text(json.dumps(spec))
            cmd += ["--spec", str(p)]
        r = sh(cmd)
        return r.returncode, r.stdout + r.stderr

    rc, _ = qrun(media, {"video": {"widht": 9999}})
    record("Q05a unknown spec key exits 2", rc == 2)
    rc, _ = qrun(media, {"audio": {"lufs_target": None}})
    record("Q06 null spec value exits 2 (no traceback)", rc == 2)
    rc, _ = qrun(media, {"audio": {"required": False}, "review": {"requires_human_signoff": True}})
    record("Q07 zero-check spec FAILS (no vacuous pass)", rc == 1)
    m2997 = tmp / "m2997.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30000/1001:d=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(m2997)])
    rc, _ = qrun(m2997, {"video": {"fps": 30}, "audio": {"required": False}})
    record("Q05b 29.97 against fps 30 FAILS", rc == 1)
    y444 = tmp / "y444.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv444p", str(y444)])
    rc, _ = qrun(y444, {"video": {"pix_fmt": "yuv420p"}, "audio": {"required": False}})
    record("Q08 yuv444p against yuv420p spec FAILS", rc == 1)
    # alpha: opaque ProRes must FAIL content, half-alpha must PASS content
    from PIL import Image
    Image.new("RGBA", (160, 90), (255, 0, 0, 255)).save(tmp / "opaque.png")
    Image.new("RGBA", (160, 90), (255, 0, 0, 128)).save(tmp / "half.png")
    for name in ("opaque", "half"):
        sh(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(tmp / f"{name}.png"),
            "-t", "1", "-r", "30", "-c:v", "prores_ks", "-profile:v", "4444",
            "-pix_fmt", "yuva444p12le", str(tmp / f"{name}.mov")])
    spec_alpha = {"overlay": {"alpha_required": True}, "audio": {"required": False}}
    rc, out = qrun(tmp / "opaque.mov", spec_alpha)
    record("Q04a opaque alpha FAILS alpha_content", "FAIL alpha_content" in out)
    rc, out = qrun(tmp / "half.mov", spec_alpha)
    record("Q04b real alpha PASSES alpha_content", "PASS alpha_content" in out)
    # sampler on a non-media file: handled error, exit 2, no traceback
    r = sh(["python3", str(SAMPLER), str(tmp / "d.json"), str(tmp / "sf")])
    record("S03 sampler on non-media exits 2 without traceback",
           r.returncode == 2 and "Traceback" not in (r.stdout + r.stderr))

    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("failed:", "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
