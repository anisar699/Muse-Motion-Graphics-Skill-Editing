#!/usr/bin/env python3
"""Muse Motion QC probe v1.1 - an authoritative delivery gate.

Usage:
  qc_probe.py <final_video> [--spec delivery_spec.json] [--report qc_report.json]

Without a spec, the default social profile applies: audio required,
integrated loudness -14 LUFS +/- 1.5, true peak at or below -1.0 dBTP.
With a spec, every field present in the spec is enforced.
Exit codes: 0 PASS, 1 FAIL, 2 tool error. A JSON report is written
when --report is given. Human-only checks are never auto-passed.
"""
import json, math, re, struct, subprocess, sys, pathlib

DEFAULT_SPEC = {
    "profile": "social_default",
    "video": {},
    "audio": {"required": True, "lufs_target": -14.0, "lufs_tolerance": 1.5, "true_peak_max_dbtp": -1.0},
    "duration": {},
    "overlay": {"alpha_required": False},
}

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)

def moov_before_mdat(path):
    try:
        data = path.read_bytes()
    except Exception:
        return None
    n = len(data); i = 0; order = []
    while i + 8 <= n:
        size = struct.unpack(">I", data[i:i+4])[0]
        typ = data[i+4:i+8].decode("latin1")
        if size == 1:
            size = struct.unpack(">Q", data[i+8:i+16])[0]
        elif size == 0:
            size = n - i
        if size < 8: break
        order.append(typ)
        if typ in ("moov", "mdat") and len(order) >= 1 and ("moov" in order and "mdat" in order):
            break
        i += size
    if "moov" not in order: return None
    if "mdat" not in order: return True
    return order.index("moov") < order.index("mdat")

def fps_of(stream):
    r = stream.get("avg_frame_rate") or "0/1"
    try:
        a, b = (float(x) for x in r.split("/"))
        return a / b if b else 0.0
    except Exception:
        return 0.0

def main():
    argv = sys.argv[1:]
    spec_path = report_path = None
    files = []
    i = 0
    while i < len(argv):
        if argv[i] == "--spec" and i + 1 < len(argv): spec_path = argv[i+1]; i += 2
        elif argv[i] == "--report" and i + 1 < len(argv): report_path = argv[i+1]; i += 2
        else: files.append(argv[i]); i += 1
    if len(files) != 1:
        print("Usage: qc_probe.py <final-video> [--spec spec.json] [--report report.json]"); return 2
    path = pathlib.Path(files[0])
    if not path.exists():
        print("QC ERROR: file not found:", path); return 2
    spec = json.loads(json.dumps(DEFAULT_SPEC))
    if spec_path:
        try:
            user = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(spec.get(k), dict): spec[k].update(v)
                else: spec[k] = v
        except Exception as exc:
            print("QC ERROR: could not read spec:", exc); return 2

    checks = []
    def check(name, ok, measured, expected):
        checks.append({"name": name, "status": "PASS" if ok else "FAIL",
                       "measured": measured, "expected": expected})
        return ok

    probe = run(["ffprobe","-v","error","-show_streams","-show_format","-of","json", str(path)])
    if probe.returncode != 0:
        print("QC ERROR: ffprobe failed:", probe.stderr[:300]); return 2
    data = json.loads(probe.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    astreams = [s for s in streams if s.get("codec_type") == "audio"]
    if not vstreams:
        check("video_stream", False, "none", "present")
        measured = {}
    else:
        vs = vstreams[0]
        measured = {"codec": vs.get("codec_name"), "width": vs.get("width"), "height": vs.get("height"),
                    "pix_fmt": vs.get("pix_fmt"), "fps": round(fps_of(vs), 3),
                    "duration_s": float(fmt.get("duration", 0) or 0)}
        print("video", measured["codec"], measured["width"], measured["height"], measured["pix_fmt"], measured["fps"])
        print("format", fmt.get("format_name"), "duration", fmt.get("duration"), "size", fmt.get("size"))
        vexp = spec.get("video") or {}
        if "width" in vexp: check("width", vs.get("width") == vexp["width"], vs.get("width"), vexp["width"])
        if "height" in vexp: check("height", vs.get("height") == vexp["height"], vs.get("height"), vexp["height"])
        if "codec" in vexp: check("codec", vs.get("codec_name") == vexp["codec"], vs.get("codec_name"), vexp["codec"])
        if "fps" in vexp: check("fps", abs(fps_of(vs) - float(vexp["fps"])) < 0.6, round(fps_of(vs), 3), vexp["fps"])
        if (spec.get("overlay") or {}).get("alpha_required"):
            pf = vs.get("pix_fmt") or ""
            check("alpha_plane", "yuva" in pf or "rgba" in pf or "argb" in pf, pf, "alpha pixel format")
    dexp = spec.get("duration") or {}
    if "expected_s" in dexp:
        d = float(fmt.get("duration", 0) or 0)
        check("duration", abs(d - float(dexp["expected_s"])) <= float(dexp.get("tolerance_s", 0.5)),
              round(d, 3), dexp["expected_s"])
    if path.suffix.lower() == ".mp4":
        mv = moov_before_mdat(path)
        if mv is not None: check("moov_faststart", mv, "moov before mdat" if mv else "moov after mdat", "moov before mdat")

    aexp = spec.get("audio") or {}
    audio_required = bool(aexp.get("required", True))
    if not astreams:
        if audio_required: check("audio_stream", False, "missing", "present [AUDIO_STREAM_MISSING]")
        measured_loud = None
    else:
        a0 = astreams[0]
        if "sample_rate" in aexp:
            check("sample_rate", int(a0.get("sample_rate", 0)) == int(aexp["sample_rate"]), a0.get("sample_rate"), aexp["sample_rate"])
        loud = run(["ffmpeg","-i",str(path),"-vn","-af","loudnorm=print_format=json","-f","null","-"])
        m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", loud.stderr)
        measured_loud = None
        if m:
            try: measured_loud = json.loads(m[-1])
            except Exception: measured_loud = None
        if measured_loud is None:
            if audio_required: check("loudness_measured", False, "no loudnorm data", "measurable programme audio")
        else:
            try: il = float(measured_loud.get("input_i"))
            except Exception: il = float("nan")
            try: tp = float(measured_loud.get("input_tp"))
            except Exception: tp = float("nan")
            print("loudness input_i", measured_loud.get("input_i"), "input_tp", measured_loud.get("input_tp"))
            if not (math.isfinite(il) and math.isfinite(tp)):
                if audio_required: check("audio_not_silent", False, f"I={measured_loud.get('input_i')} TP={measured_loud.get('input_tp')}", "finite programme loudness [AUDIO_SILENT]")
            else:
                if "lufs_target" in aexp:
                    tol = float(aexp.get("lufs_tolerance", 1.5))
                    check("loudness_lufs", abs(il - float(aexp["lufs_target"])) <= tol, il, f"{aexp['lufs_target']} +/- {tol}")
                if "true_peak_max_dbtp" in aexp:
                    check("true_peak", tp <= float(aexp["true_peak_max_dbtp"]), tp, f"<= {aexp['true_peak_max_dbtp']}")

    failed = [c for c in checks if c["status"] == "FAIL"]
    status = "FAIL" if failed else "PASS"
    report = {"file": str(path), "profile": spec.get("profile", "custom"), "status": status,
              "checks": checks,
              "note": "Automated checks only. Narrative truth, visual taste, caption accuracy and face protection on moving footage still require human sign-off."}
    if report_path:
        pathlib.Path(report_path).write_text(json.dumps(report, indent=1), encoding="utf-8")
    for c in checks:
        print(f"{c['status']} {c['name']}: measured={c['measured']} expected={c['expected']}")
    print("QC", status)
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
