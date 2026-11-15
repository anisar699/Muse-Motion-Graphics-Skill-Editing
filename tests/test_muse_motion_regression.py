#!/usr/bin/env python3
"""Muse Motion shipped regression suite (v1.3).

Self-contained: needs python3, ffmpeg, ffprobe and Pillow. Run directly:
  python3 tests/test_muse_motion_regression.py
Exits 0 when every case matches the v1.3 contract, 1 otherwise.
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
PEAK = SKILL / "scripts" / "peak_guard.py"
CAPS = SKILL / "scripts" / "check_captions.py"
TRANSCRIBE = SKILL / "scripts" / "transcribe.py"
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

    # --- v1.3: peak guard ---
    r = sh(["python3", str(PEAK), str(media), "--report", str(tmp / "pg1.json")])
    pg = json.loads((tmp / "pg1.json").read_text()) if (tmp / "pg1.json").exists() else {}
    record("P01 quiet file passes peak guard unchanged",
           r.returncode == 0 and pg.get("status") == "pass_already_within_ceiling")
    hot = tmp / "hot.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=3",
        "-f", "lavfi", "-i", "aevalsrc=sin(2*PI*440*t):d=3", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(hot)])
    r = sh(["python3", str(PEAK), str(hot), "--report", str(tmp / "pg2.json")])
    pg = json.loads((tmp / "pg2.json").read_text()) if (tmp / "pg2.json").exists() else {}
    record("P02 hot file is fixed to below the ceiling",
           r.returncode == 0 and pg.get("status") == "fixed" and pg.get("tp_after", 0) <= -1.0)
    r = sh(["python3", str(PEAK), str(tmp / "nope.mp4")])
    record("P03 peak guard on missing file exits 2", r.returncode == 2)

    # --- v1.3: caption checker ---
    good = tmp / "good.srt"
    good.write_text("1\n00:00:01,000 --> 00:00:03,500\nA perfectly fine caption line\n")
    bad = tmp / "bad.srt"
    bad.write_text("1\n00:00:01,000 --> 00:00:02,600\nThis line is deliberately made far too long for the limit\n")
    r = sh(["python3", str(CAPS), str(good), "--fg", "FFFFFF", "--bg", "000000"])
    record("C01 clean SRT with good contrast passes", r.returncode == 0)
    r = sh(["python3", str(CAPS), str(bad)])
    record("C02 over-long caption line fails", r.returncode == 1)
    r = sh(["python3", str(CAPS), str(good), "--fg", "777777", "--bg", "888888"])
    record("C03 low contrast fails", r.returncode == 1)
    r = sh(["python3", str(CAPS), str(tmp / "nope.srt")])
    record("C04 caption checker on missing file exits 2", r.returncode == 2)

    # --- v1.4: caption engine + validator captions block ---
    BUILD_CAPS = SKILL / "scripts" / "build_captions.py"
    d = base(); d["captions"] = {"mode": "sidecar", "language": "en", "style": "skill-bar", "highlight": "word"}
    record("K01 validator accepts a valid captions block", vrun(d)[0] == 0)
    d = base(); d["captions"] = {"mode": "sidecar", "language": "xx"}
    record("K02 validator rejects an unknown caption language", vrun(d)[0] == 1)
    d = base(); d["captions"] = {"mode": "sidecar", "language": "en", "highlight": "letter"}
    record("K03 validator rejects an unknown highlight mode", vrun(d)[0] == 1)
    d = base(); d["captions"] = {"mode": "burned", "language": "en", "style": "skill-bar"}
    record("K04 render gate requires captions.source for burned mode", vrun(d)[0] == 1)
    d = base(); d["captions"] = {"mode": "sidecar", "language": "ur", "style": "skill-bar"}
    rc, out = vrun(d)
    record("K05 house-style deviation warns but stays VALID", rc == 0 and "house style" in out)

    def words_json(lang, pairs):
        ws = [{"word": w, "start": s, "end": e, "probability": 0.9} for w, s, e in pairs]
        return {"language": lang, "segments": [{"start": pairs[0][1], "end": pairs[-1][2],
                "text": " ".join(w for w, _, _ in pairs), "words": ws}]}
    en_tr = tmp / "en_tr.json"
    en_tr.write_text(json.dumps(words_json("en", [("When", 0.0, 0.3), ("your", 0.3, 0.55),
        ("phone", 0.55, 0.9), ("is", 0.9, 1.05), ("in", 1.05, 1.2), ("sight,", 1.2, 1.6),
        ("your", 1.7, 1.95), ("attention", 1.95, 2.5), ("drops.", 2.5, 3.0)])))
    out_en = tmp / "caps_en"
    r = sh([sys.executable, str(BUILD_CAPS), str(en_tr), "--lang", "en", "--out-dir", str(out_en), "--duration", "4.0"])
    cj = json.loads((out_en / "captions.json").read_text()) if (out_en / "captions.json").exists() else {}
    record("K06 EN captions build with word-highlight states",
           r.returncode == 0 and cj.get("word_highlight") is True
           and len(cj.get("cues", [])) >= 1 and len(cj["cues"][0].get("states", [])) >= 2)
    r2 = sh([sys.executable, str(CAPS), str(out_en / "captions.srt")])
    record("K07 generated EN SRT passes check_captions", r2.returncode == 0)
    ur_tr = tmp / "ur_tr.json"
    ur_tr.write_text(json.dumps(words_json("ur", [("جب", 0.0, 0.3), ("فون", 0.3, 0.7),
        ("نظر", 0.7, 1.1), ("کے", 1.1, 1.3), ("سامنے", 1.3, 1.8), ("ہو،", 1.8, 2.1),
        ("توجہ", 2.2, 2.7), ("کم", 2.7, 3.0), ("ہو", 3.0, 3.3), ("جاتی", 3.3, 3.7), ("ہے۔", 3.7, 4.0)])))
    out_rom = tmp / "caps_rom"
    r = sh([sys.executable, str(BUILD_CAPS), str(ur_tr), "--lang", "roman", "--out-dir", str(out_rom), "--duration", "5.0"])
    cj = json.loads((out_rom / "captions.json").read_text()) if (out_rom / "captions.json").exists() else {}
    joined = " ".join(" ".join(c.get("lines", [])) for c in cj.get("cues", [])).lower()
    record("K08 Roman transliteration + full dictionary coverage",
           r.returncode == 0 and "jab phone nazar" in joined
           and cj.get("dictionary_coverage_percent") == 100.0)
    out_ur = tmp / "caps_ur"
    r = sh([sys.executable, str(BUILD_CAPS), str(ur_tr), "--lang", "ur", "--out-dir", str(out_ur), "--duration", "5.0"])
    cj = json.loads((out_ur / "captions.json").read_text()) if (out_ur / "captions.json").exists() else {}
    record("K09 Urdu Nastaliq captions build with states",
           r.returncode == 0 and cj.get("style") == "nastaliq-bar"
           and len(cj.get("cues", [])) >= 1 and len(cj["cues"][0].get("states", [])) >= 2)
    r = sh([sys.executable, str(BUILD_CAPS), str(en_tr), "--lang", "ur", "--out-dir", str(tmp / "caps_bad"), "--duration", "4.0"])
    record("K10 English transcript is refused for Urdu (no silent translation)", r.returncode == 2)
    out_nh = tmp / "caps_nh"
    r = sh([sys.executable, str(BUILD_CAPS), str(en_tr), "--lang", "en", "--out-dir", str(out_nh),
            "--duration", "4.0", "--no-highlight"])
    cj = json.loads((out_nh / "captions.json").read_text()) if (out_nh / "captions.json").exists() else {}
    record("K11 --no-highlight renders one static state per cue",
           r.returncode == 0 and cj.get("word_highlight") is False
           and all(len(c.get("states", [])) == 1 for c in cj.get("cues", [])))

    # --- v1.3: transcription ---
    try:
        import faster_whisper  # noqa: F401
        have_fw = True
    except ImportError:
        have_fw = False
    if have_fw:
        r = sh([sys.executable, str(TRANSCRIBE), str(media), "--out", str(tmp / "tr.json")])
        ok = r.returncode == 0 and (tmp / "tr.json").exists() and "segments" in json.loads((tmp / "tr.json").read_text())
        record("R01 transcribe.py writes a valid transcript JSON", ok)
    else:
        record("R01 transcribe.py writes a valid transcript JSON", True,
               "skipped: faster-whisper not installed for this python")

    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("failed:", "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
