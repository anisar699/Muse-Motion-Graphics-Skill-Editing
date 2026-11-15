#!/usr/bin/env python3
"""Muse Motion shipped regression suite (v1.7).

Self-contained: needs python3, ffmpeg, ffprobe and Pillow. Run directly:
  python3 tests/test_muse_motion_regression.py
Exits 0 when every case matches the v1.7 contract, 1 otherwise.
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


def record_skip(name, detail=""):
    """Honest SKIP (v1.5, F0-3): a skipped case is reported as skipped and
    is never counted as a pass."""
    RESULTS.append((name, None, detail))
    print("SKIP " + name + (f"  [{detail}]" if detail else ""))


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
    rc, out = vrun(d)
    record("T06 reveal_sync without on_screen_copy is INVALID", rc == 1 and "reveal_sync requires on_screen_copy" in out)
    d = base(); d["version"] = True
    rc, out = vrun(d)
    record("T09 version true is INVALID", rc == 1 and "version must be the integer 1" in out)
    d = base(); d["beats"][0].pop("id")
    rc, out = vrun(d)
    record("T10 beat without id is INVALID", rc == 1 and "a non-empty string id is required" in out)
    d = base(); d["beats"][0]["transtion_in"] = "banana-swirl"
    rc, out = vrun(d)
    record("T13 unknown beat key is INVALID", rc == 1 and "unknown key" in out)
    d = base(); d["beats"][0].update({"treatment": "CLEAN_PRESENTER", "layout": "banana"})
    rc, out = vrun(d)
    record("T20 non-rect layout is INVALID for any treatment", rc == 1 and "layout must be null or a rectangle" in out)
    d = base(); d["beats"][0].update({"start": 1.0, "end": 1.5, "on_screen_copy": ["X" * 500]})
    rc, out = vrun(d)
    record("T21 500 chars in 0.5s is INVALID (reading speed)", rc == 1 and "on-screen copy runs at" in out)
    d = base(); d["format"] = {"width": 1921, "height": 1081, "fps": 30, "aspect": "16:9"}
    rc, out = vrun(d)
    record("T16 odd canvas dims are INVALID", rc == 1 and "must be even" in out)
    d = base(); d["format"] = {"width": 1920, "height": 1080, "fps": 1000, "aspect": "16:9"}
    rc, out = vrun(d)
    record("T17 fps 1000 is INVALID", rc == 1 and "is not a standard frame rate" in out)
    d = base(); d["format"] = {"width": 1080, "height": 1920, "fps": 30, "aspect": "4:7"}
    record("T22b aspect 4:7 for 1080x1920 is INVALID", vrun(d)[0] == 1)
    d = base(); d["source"] = {"path": str(media), "duration_s": 10.5}
    d["beats"][0].update({"end": 10.5})
    rc, out = vrun(d)
    record("T24 declared duration beyond probed is INVALID", rc == 1 and "differs from probed duration" in out)
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
    # A TRUE zero-check scenario needs a file no default check can fire on:
    # no audio stream (loudness/true-peak defaults would otherwise run and
    # fail first - which is exactly how this case used to pass vacuously).
    silent = tmp / "silent.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(silent)])
    rc, out = qrun(silent, {"audio": {"required": False}, "review": {"requires_human_signoff": True},
                            "faststart_required": False})
    record("Q07 zero-check spec FAILS (no vacuous pass)", rc == 1 and "FAIL checks_executed" in out)
    m2997 = tmp / "m2997.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30000/1001:d=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(m2997)])
    rc, out = qrun(m2997, {"video": {"fps": 30}, "audio": {"required": False}})
    record("Q05b 29.97 against fps 30 FAILS", rc == 1 and "FAIL fps" in out)
    y444 = tmp / "y444.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=320x240:r=30:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv444p", str(y444)])
    rc, out = qrun(y444, {"video": {"pix_fmt": "yuv420p"}, "audio": {"required": False}})
    record("Q08 yuv444p against yuv420p spec FAILS", rc == 1 and "FAIL pix_fmt" in out)
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
    out = r.stdout + r.stderr
    record("C02 over-long caption line fails", r.returncode == 1 and "chars > 42" in out)
    r = sh(["python3", str(CAPS), str(good), "--fg", "777777", "--bg", "888888"])
    out = r.stdout + r.stderr
    record("C03 low contrast fails", r.returncode == 1 and "contrast" in out and "< 4.5:1" in out)
    r = sh(["python3", str(CAPS), str(tmp / "nope.srt")])
    record("C04 caption checker on missing file exits 2", r.returncode == 2)

    # --- v1.4: caption engine + validator captions block ---
    BUILD_CAPS = SKILL / "scripts" / "build_captions.py"
    d = base(); d["captions"] = {"mode": "sidecar", "language": "en", "style": "skill-bar", "highlight": "word"}
    record("K01 validator accepts a valid captions block", vrun(d)[0] == 0)
    d = base(); d["captions"] = {"mode": "sidecar", "language": "xx"}
    rc, out = vrun(d)
    record("K02 validator rejects an unknown caption language", rc == 1 and "captions.language must be one of" in out)
    d = base(); d["captions"] = {"mode": "sidecar", "language": "en", "highlight": "letter"}
    rc, out = vrun(d)
    record("K03 validator rejects an unknown highlight mode", rc == 1 and "captions.highlight must be one of" in out)
    d = base(); d["captions"] = {"mode": "burned", "language": "en", "style": "skill-bar"}
    rc, out = vrun(d)
    record("K04 render gate requires captions.source for burned mode", rc == 1 and "captions.source" in out and "is required" in out)
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

    # --- v1.6: cue-group repairs (user audit 2026-11-15) ---
    def cap_texts(tr_path, out_name, dur, *extra):
        out_d = tmp / out_name
        r = sh([sys.executable, str(BUILD_CAPS), str(tr_path), "--lang", "en",
                "--out-dir", str(out_d), "--duration", str(dur), *extra])
        if r.returncode != 0 or not (out_d / "captions.json").exists():
            return None
        cj2 = json.loads((out_d / "captions.json").read_text())
        return [" ".join(c.get("lines", [])) for c in cj2.get("cues", [])]
    orph = tmp / "orph.json"
    orph.write_text(json.dumps(words_json("en", [(w, i * 0.3, i * 0.3 + 0.28) for i, w in enumerate(
        ["aaaaa", "bbbbb", "ccccc", "ddddd", "eeeee", "fffff", "gggggggg."])])))
    texts = cap_texts(orph, "caps_orph", 3.0, "--max-chars", "20")
    record("K12 orphan tail word merges into the previous cue",
           texts is not None and len(texts) == 2 and "gggggggg." in texts[-1]
           and all(len(t.split()) > 1 for t in texts))
    shift = tmp / "shift.json"
    shift.write_text(json.dumps(words_json("en", [(w, i * 0.35, i * 0.35 + 0.32) for i, w in enumerate(
        ["Silent", "majestic", "station", "drifting", "in", "silence", "we",
         "watched", "the", "world", "turn", "below."])])))
    texts = cap_texts(shift, "caps_shift", 5.0)
    record("K13 group ending on a function word shifts it forward",
           texts is not None and any(t.startswith("in silence") for t in texts)
           and not any(t.endswith(" in") for t in texts))
    swal = tmp / "swal.json"
    swal.write_text(json.dumps(words_json("en", [(w, i * 0.35, i * 0.35 + 0.32) for i, w in enumerate(
        ["Giant", "batteries", "store", "energy", "for", "the", "night", "side",
         "effects", "linger", "here", "today."])])))
    texts = cap_texts(swal, "caps_swal", 5.0)
    record("K14 short compound word is swallowed, not split off",
           texts is not None and any("night side" in t for t in texts))
    guard = tmp / "guard.json"
    guard.write_text(json.dumps(words_json("en", [(w, i * 0.35, i * 0.35 + 0.32) for i, w in enumerate(
        ["The", "old", "silent", "station", "drifting", "and", "waits.",
         "A", "city", "sleeps."])])))
    texts = cap_texts(guard, "caps_guard", 5.0)
    record("K15 a new sentence's first word is never swallowed",
           texts is not None and len(texts) == 2 and texts[1].startswith("A city")
           and not any("waits. A" in t for t in texts))
    d = base(); d["captions"] = {"mode": "burned", "language": "en", "style": "skill-bar", "highlight": "word"}
    d["beats"][0]["layout"] = {"x": 20, "y": 250, "width": 200, "height": 80}
    rc, out = vrun(d, "--draft")
    record("K16 card parked in the caption zone warns (owner rule)",
           rc == 0 and "caption zone" in out and "PLACEMENT" in out)
    d["beats"][0]["layout"] = {"x": 20, "y": 20, "width": 200, "height": 80}
    rc, out = vrun(d, "--draft")
    record("K17 top-zone card does not warn",
           rc == 0 and "caption zone" not in out)

    # --- v1.5: Phase-0 fixes (F0-1, F0-2, F0-4, F0-5, F0-6) ---
    ALPHA_SPEC_FILE = SKILL / "templates" / "delivery-spec-alpha-overlay.json"
    VP9_SPEC_FILE = SKILL / "templates" / "delivery-spec-vp9-alpha-overlay.json"
    r = sh(["python3", str(QC), str(tmp / "half.mov"), "--spec", str(ALPHA_SPEC_FILE)])
    out = r.stdout + r.stderr
    record("N01 F0-1 ProRes master passes its spec without faststart",
           r.returncode == 0 and "moov_faststart" not in out)
    rc, out = qrun(media, {"faststart_required": True, "audio": {"required": False}})
    record("N02 F0-1 web spec still FAILS an mp4 without faststart",
           rc == 1 and "FAIL moov_faststart" in out)
    rc, out = qrun(media, {"audio": {"required": False}})
    record("N03 F0-1 unset policy defaults to required for .mp4",
           rc == 1 and "FAIL moov_faststart" in out)
    for name in ("opaque", "half"):
        sh(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(tmp / f"{name}.png"),
            "-t", "1", "-r", "30", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
            "-b:v", "200k", "-auto-alt-ref", "0", str(tmp / f"{name}.webm")])
        sh(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(tmp / f"{name}.png"),
            "-t", "1", "-r", "30", "-c:v", "ffv1", "-pix_fmt", "yuva444p16le", str(tmp / f"{name}.mkv")])
    r = sh(["python3", str(QC), str(tmp / "half.webm"), "--spec", str(VP9_SPEC_FILE)])
    record("N04 F0-5 VP9 alpha overlay passes the VP9 spec", r.returncode == 0)
    r = sh(["python3", str(QC), str(tmp / "opaque.webm"), "--spec", str(VP9_SPEC_FILE)])
    out = r.stdout + r.stderr
    record("N05 F0-5 opaque VP9 FAILS alpha_content under the VP9 spec",
           r.returncode == 1 and "FAIL alpha_content" in out)
    rc, out = qrun(tmp / "opaque.mkv", spec_alpha)
    record("N06 F0-6 16-bit opaque alpha FAILS on the 65535 scale",
           rc == 1 and "FAIL alpha_content" in out and "of 65535" in out)
    rc, out = qrun(tmp / "opaque.webm", spec_alpha)
    record("N07 F0-6 8-bit opaque alpha FAILS on the 255 scale",
           rc == 1 and "FAIL alpha_content" in out and "of 255" in out)
    sf = tmp / "sf"
    d = base()
    dp = tmp / "dir.json"; dp.write_text(json.dumps(d))
    sh(["python3", str(SAMPLER), str(media), str(sf), "--directive", str(dp)])
    sh(["python3", str(SAMPLER), str(media), str(sf)])
    stale = [p.name for p in sf.glob("frame_*.png") if "b1" in p.name]
    record("N08 F0-4 stale frames from an earlier sampler run are removed", stale == [])
    tpl2 = json.loads(TEMPLATE.read_text())
    beats = []
    for i in range(10):
        b = copy.deepcopy(tpl2["beats"][0])
        b.update({"id": f"nb{i}", "start": 0.5 + i * 0.9, "end": 1.2 + i * 0.9,
                  "reveal_sync": [{"element": "x", "time": 0.8 + i * 0.9}]})
        beats.append(b)
    tpl2["beats"] = beats
    dp2 = tmp / "dir10.json"; dp2.write_text(json.dumps(tpl2))
    sf2 = tmp / "sf2"
    sh(["python3", str(SAMPLER), str(media), str(sf2), "--directive", str(dp2)])
    man = json.loads((sf2 / "frames_manifest.json").read_text())
    record("N09 F0-4 many frames paginate into multiple contact sheets",
           len(man.get("contact_sheets", [])) == 2 and len(man.get("frames", [])) > 24)
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        "smptehdbars=size=320x180:rate=30:duration=2,setparams=color_primaries=bt2020:color_trc=bt2020-10:colorspace=bt2020nc",
        "-c:v", "libx264", "-pix_fmt", "yuv420p10le", str(tmp / "wide.mp4")])
    spec709 = {"video": {"color_space": "bt709", "color_primaries": "bt709", "color_transfer": "bt709"},
               "audio": {"required": False}, "faststart_required": False}
    rc, out = qrun(tmp / "wide.mp4", spec709)
    n10a = rc == 1 and "FAIL color_space" in out
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(tmp / "wide.mp4"), "-vf",
        "colorspace=all=bt709:iall=bt2020:itrc=bt2020-10:iprimaries=bt2020:ispace=bt2020nc",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(tmp / "wide_conv.mp4")])
    rc, out = qrun(tmp / "wide_conv.mp4", spec709)
    record("N10 F0-2 wide-gamut source FAILS bt709 spec; converted pixels PASS",
           n10a and rc == 0 and "PASS color_space" in out)

    # --- v1.7: fourth audit fixes (N-01..N-04, C-01, H-01..H-05, M-02/03/05/08) ---
    foreign = tmp / "foreign"
    foreign.mkdir()
    (foreign / "frame_0000.png").write_bytes(b"RENDER OUTPUT - NOT THE SAMPLER'S")
    sh(["python3", str(SAMPLER), str(media), str(foreign)])
    record("V01 N-01 sampler never deletes foreign frame files",
           (foreign / "frame_0000.png").read_bytes() == b"RENDER OUTPUT - NOT THE SAMPLER'S")
    half_png = tmp / "half.png"
    sh([sys.executable, "-c", "from PIL import Image; Image.new('RGBA', (64, 64), (255, 0, 0, 128)).save(r'" + str(half_png) + "')"])
    sh(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(half_png), "-t", "1",
        "-c:v", "png", "-pix_fmt", "rgba64be", str(tmp / "half64.mov")])
    rc, out = qrun(tmp / "half64.mov", spec_alpha)
    record("V02 N-02 half-transparent PNG-codec alpha passes on the 65535 scale",
           "PASS alpha_content" in out and "of 65535" in out)
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "libvpx-vp9",
        "-pix_fmt", "yuv420p", "-c:a", "libopus", str(tmp / "fs.webm")])
    rc, out = qrun(tmp / "fs.webm", {"faststart_required": True})
    record("V03 N-04 faststart_required on WebM FAILs loudly, never silently",
           rc == 1 and "FAIL faststart_required" in out)
    c01_pairs = ([("aa", 0.0, 2.2), ("bb", 2.3, 4.5), ("cc", 4.6, 6.8)]
                 + [(w, 6.9 + i * 0.1, 7.0 + i * 0.1) for i, w in enumerate(
                     ["ddddd", "eeeee", "fffff", "ggggg", "hhhhh", "iiiii", "jjjjj", "kkkkk", "lllll"])])
    c01 = tmp / "c01.json"
    c01.write_text(json.dumps(words_json("en", c01_pairs)))
    out_c01 = tmp / "caps_c01"
    r = sh([sys.executable, str(BUILD_CAPS), str(c01), "--lang", "en",
            "--out-dir", str(out_c01), "--duration", "8"])
    cj = json.loads((out_c01 / "captions.json").read_text()) if (out_c01 / "captions.json").exists() else {}
    spoken = {w: s for w, s, _ in c01_pairs}
    anchored = bool(cj.get("cues")) and all(
        c["start"] >= spoken[c["lines"][0].split()[0]] - 0.35 for c in cj["cues"])
    record("V04 C-01 no cue starts more than 0.35s before its first word",
           r.returncode == 0 and anchored)
    h04 = tmp / "h04.json"
    h04.write_text(json.dumps(words_json("en",
        [(f"w{i:02d}xx", i * 0.24, i * 0.24 + 0.2) for i in range(20)])))
    out_h04 = tmp / "caps_h04"
    r = sh([sys.executable, str(BUILD_CAPS), str(h04), "--lang", "en",
            "--out-dir", str(out_h04), "--duration", "5.0"])
    cj = json.loads((out_h04 / "captions.json").read_text()) if (out_h04 / "captions.json").exists() else {}
    record("V05 H-04 no cue runs past the timeline duration; clamps declared",
           r.returncode == 0 and cj.get("cues") and cj["cues"][-1]["end"] <= 5.001
           and cj.get("cues_clamped_to_duration", 0) >= 1)
    hot = tmp / "hot.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
        "aevalsrc=0.9*sin(2*PI*440*t):d=2:s=48000", "-af", "volume=6dB",
        "-c:a", "aac", str(hot)])
    multi = tmp / "multi.mp4"
    (tmp / "sub.srt").write_text("1\n00:00:00,000 --> 00:00:01,500\nHello subtitle\n")
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
        "-i", str(hot), "-f", "lavfi", "-i", "sine=frequency=880:duration=2:sample_rate=48000",
        "-i", str(tmp / "sub.srt"), "-map", "0:v", "-map", "1:a", "-map", "2:a", "-map", "3:s",
        "-c:v", "libx264", "-c:a", "aac", "-c:s", "mov_text", str(multi)])
    r = sh([sys.executable, str(PEAK), str(multi)])
    types = []
    pf = tmp / "multi-peakfixed.mp4"
    if pf.exists():
        pr = sh(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                 "-of", "csv=p=0", str(pf)])
        types = sorted(pr.stdout.split())
    record("V06 H-02 peak_guard preserves every stream (2 audio + subtitle)",
           r.returncode == 0 and types == ["audio", "audio", "subtitle", "video"])
    out_small = tmp / "caps_small"
    sh([sys.executable, str(BUILD_CAPS), str(en_tr), "--lang", "en",
        "--out-dir", str(out_small), "--video", "640x360", "--duration", "4.0"])
    d = base(); d["captions"] = {"mode": "burned", "language": "ur", "style": "nastaliq-bar",
                                 "highlight": "word", "source": str(out_small / "captions.json")}
    rc, out = vrun(d)
    record("V07 H-01 render gate rejects a captions build that mismatches the directive",
           rc == 1 and "does not match captions.language" in out)
    d = base(); d["captions"] = {"mode": "burned", "language": "en", "style": "skill-bar",
                                 "highlight": "word", "source": str(out_small / "captions.json")}
    rc, out = vrun(d)
    record("V08 H-01 render gate accepts a captions build that matches",
           rc == 0 and "VALID" in out)
    lie = tmp / "lie.json"
    lie.write_text(json.dumps(words_json("ur", [("Hello", 0.0, 0.3), ("world", 0.3, 0.7),
                                                ("this", 0.7, 1.0), ("is", 1.0, 1.3)])))
    r = sh([sys.executable, str(BUILD_CAPS), str(lie), "--lang", "ur",
            "--out-dir", str(tmp / "caps_lie"), "--duration", "2"])
    record("V09 M-03 a transcript whose label lies about its script is refused",
           r.returncode == 2 and "Arabic script" in (r.stdout + r.stderr))
    srt3 = tmp / "three.srt"
    srt3.write_text("1\n00:00:00,000 --> 00:00:02,000\nline one\nline two\nline three\n")
    r = sh([sys.executable, str(CAPS), str(srt3)])
    record("V10 M-05 checker errors on a cue with more than 2 lines",
           r.returncode == 1 and "3 lines > 2" in (r.stdout + r.stderr))
    srtb = tmp / "backwards.srt"
    srtb.write_text("1\n00:00:02,000 --> 00:00:01,000\nbackwards cue\n")
    r = sh([sys.executable, str(CAPS), str(srtb)])
    record("V11 M-05 checker errors on a backwards cue",
           r.returncode == 1 and "backwards cue" in (r.stdout + r.stderr))
    badj = tmp / "bad.json"; badj.write_text("{not json")
    r = sh([sys.executable, str(BUILD_CAPS), str(badj), "--lang", "en"])
    record("V12 M-01 malformed transcript JSON is a clean error, no traceback",
           r.returncode == 2 and "Traceback" not in (r.stdout + r.stderr))
    miss = tmp / "missing_end.json"
    miss.write_text(json.dumps({"language": "en", "segments": [
        {"start": 0, "end": 1, "text": "x", "words": [{"word": "Hello", "start": 0.0}]}]}))
    r = sh([sys.executable, str(BUILD_CAPS), str(miss), "--lang", "en"])
    record("V13 M-08 a word missing its end time is a clean error",
           r.returncode == 2 and "malformed" in (r.stdout + r.stderr))
    rare = tmp / "rare.json"
    rare.write_text(json.dumps(words_json("ur", [("خلاباز", 0.0, 0.4), ("مائیکروسکوپ", 0.4, 0.9),
                                                 ("سیارچہ", 0.9, 1.3), ("دوربین", 1.3, 1.7)])))
    r = sh([sys.executable, str(BUILD_CAPS), str(rare), "--lang", "roman",
            "--out-dir", str(tmp / "caps_rare"), "--duration", "2"])
    record("V14 M-02 roman build fails loudly below 60 percent dictionary coverage",
           r.returncode == 1 and "coverage" in (r.stdout + r.stderr))
    out_vert = tmp / "caps_vert"
    r = sh([sys.executable, str(BUILD_CAPS), str(en_tr), "--lang", "en",
            "--out-dir", str(out_vert), "--video", "1080x1920", "--duration", "4.0"])
    margin_ok = False
    if r.returncode == 0 and (out_vert / "captions.json").exists():
        import numpy as _np
        from PIL import Image as _Im
        cjv = json.loads((out_vert / "captions.json").read_text())
        im = _Im.open(out_vert / cjv["cues"][0]["png"]).convert("RGBA")
        rows = _np.where(_np.array(im)[:, :, 3].sum(axis=1) > 0)[0]
        margin_ok = len(rows) > 0 and (1920 - 1 - int(rows.max())) >= 440
    record("V15 H-05 portrait captions clear the platform UI band (>=440px)",
           r.returncode == 0 and margin_ok)
    burn_src = tmp / "burn_src.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(burn_src)])
    out_burn = tmp / "caps_burn"
    sh([sys.executable, str(BUILD_CAPS), str(en_tr), "--lang", "en",
        "--out-dir", str(out_burn), "--video", "320x240", "--duration", "2"])
    r = sh(["ffmpeg", "-y", "-i", str(burn_src), "-f", "concat", "-safe", "0",
            "-i", "layer.ffconcat", "-filter_complex",
            "[0:v][1:v]overlay=0:0:format=auto:eof_action=pass,format=yuv420p[out]",
            "-map", "[out]", "-map", "0:a?", "-c:v", "libx264", "-profile:v", "high",
            "-crf", "18", "-c:a", "copy", "burned.mp4"], cwd=str(out_burn))
    record("V16 M-06 the documented caption burn command runs as written",
           r.returncode == 0 and (out_burn / "burned.mp4").exists())

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
        cwd_dir = tmp / "cwd_out"
        cwd_dir.mkdir()
        stray = tmp / "transcript.json"
        if stray.exists():
            stray.unlink()
        r = sh([sys.executable, str(TRANSCRIBE), str(media)], cwd=str(cwd_dir))
        record("V17 M-07 transcribe default output lands in the CWD, not the source folder",
               r.returncode == 0 and (cwd_dir / f"{media.stem}.transcript.json").exists()
               and not stray.exists())
    else:
        record_skip("R01 transcribe.py writes a valid transcript JSON",
                    "faster-whisper not installed for this python")

    failed = [n for n, ok, _ in RESULTS if ok is False]
    skipped = [n for n, ok, _ in RESULTS if ok is None]
    passed = sum(1 for _, ok, _ in RESULTS if ok is True)
    print(f"\n{passed}/{len(RESULTS)} passed" + (f", {len(skipped)} skipped" if skipped else ""))
    if skipped:
        print("skipped:", "; ".join(skipped))
    if failed:
        print("failed:", "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
