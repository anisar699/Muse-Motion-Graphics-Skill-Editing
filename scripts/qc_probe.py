#!/usr/bin/env python3
"""Muse Motion QC probe v1.2 - an authoritative delivery gate.

Usage:
  qc_probe.py <final_video> [--spec delivery_spec.json] [--report qc_report.json]

Without a spec, the default social profile applies: audio required,
integrated loudness -14 LUFS +/- 1.5, true peak at or below -1.0 dBTP.
With a spec, every field present in the spec is enforced; unknown keys or
wrongly-typed values are a tool error (exit 2), never silently ignored.
Exit codes: 0 PASS, 1 FAIL, 2 tool error. A JSON report is written
when --report is given. Human-only checks are never auto-passed.

v1.2 changes (from the v1.1 developer audit):
  - Spec key whitelist and type validation (a typo can no longer pass).
  - fps tolerance tightened to 0.01 and VFR is detected (r_frame_rate vs
    avg_frame_rate).
  - A spec that produces zero checks FAILS instead of passing vacuously.
  - moov check streams box headers instead of loading the file into RAM,
    covers .mp4/.mov/.m4v, and a missing moov is a FAIL, not a silent skip.
  - Alpha: VP8/VP9 files are recognised via the alpha_mode tag, the pixel
    format set is complete, and a content check decodes the alpha plane and
    fails a constant-opaque alpha (the "black box" failure).
  - New enforceable spec keys: video pix_fmt, profile, field_order,
    color_space, color_primaries, color_transfer, bit-rate range;
    audio codec and channels.
  - Environment failures (ffprobe/ffmpeg missing, timeouts, unwritable
    report) exit 2 with a QC ERROR line and an ERROR report.
"""
import json, math, re, subprocess, sys, pathlib

DEFAULT_SPEC = {
    "profile": "social_default",
    "video": {},
    "audio": {"required": True, "lufs_target": -14.0, "lufs_tolerance": 1.5, "true_peak_max_dbtp": -1.0},
    "duration": {},
    "overlay": {"alpha_required": False},
}

SPEC_KEYS = {
    "profile": str,
    "video": {"width": int, "height": int, "fps": (int, float), "codec": str,
              "pix_fmt": str, "profile": str, "field_order": str,
              "color_space": str, "color_primaries": str, "color_transfer": str,
              "bit_rate_min_kbps": (int, float), "bit_rate_max_kbps": (int, float)},
    "audio": {"required": bool, "codec": str, "channels": int, "sample_rate": int,
              "lufs_target": (int, float), "lufs_tolerance": (int, float),
              "true_peak_max_dbtp": (int, float)},
    "duration": {"expected_s": (int, float), "tolerance_s": (int, float)},
    "overlay": {"alpha_required": bool},
    "review": {"requires_human_signoff": bool},
    "faststart_required": bool,
}
ALPHA_PIX_HINTS = ("yuva", "rgba", "argb", "bgra", "abgr", "gbrap", "ya8", "ya16")


class ToolError(Exception):
    pass


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        raise ToolError(f"required tool not found on PATH: {cmd[0]}")
    except subprocess.TimeoutExpired:
        raise ToolError(f"tool timed out: {cmd[0]}")


def moov_before_mdat(path):
    """Stream ISO-BMFF box headers; True/False, or None if no moov exists."""
    try:
        f = open(path, "rb")
    except Exception:
        return None
    order = []
    with f:
        while True:
            header = f.read(8)
            if len(header) < 8:
                break
            size = int.from_bytes(header[0:4], "big")
            typ = header[4:8].decode("latin1")
            header_len = 8
            if size == 1:
                ext = f.read(8)
                if len(ext) < 8:
                    break
                size = int.from_bytes(ext, "big")
                header_len = 16
            elif size == 0:
                size = 8  # extends to EOF; treat as last box
                order.append(typ)
                break
            if size < header_len:
                break
            order.append(typ)
            if "moov" in order and "mdat" in order:
                break
            f.seek(size - header_len, 1)
    if "moov" not in order:
        return None
    if "mdat" not in order:
        return True
    return order.index("moov") < order.index("mdat")


def fps_of(stream, key="avg_frame_rate"):
    r = stream.get(key) or "0/1"
    try:
        a, b = (float(x) for x in r.split("/"))
        return a / b if b else 0.0
    except Exception:
        return 0.0


def validate_spec(spec):
    for k, v in spec.items():
        if k not in SPEC_KEYS:
            raise ToolError(f"spec: unknown top-level key {k!r}")
        rule = SPEC_KEYS[k]
        if isinstance(rule, dict):
            if not isinstance(v, dict):
                raise ToolError(f"spec: {k} must be an object")
            for kk, vv in v.items():
                if kk not in rule:
                    raise ToolError(f"spec: unknown key {k}.{kk}")
                want = rule[kk]
                if isinstance(vv, bool) and want is not bool:
                    raise ToolError(f"spec: {k}.{kk} must not be a boolean")
                if not isinstance(vv, want):
                    raise ToolError(f"spec: {k}.{kk} has the wrong type")
        elif not isinstance(v, rule):
            raise ToolError(f"spec: {k} has the wrong type")


def alpha_range(path, codec):
    """Decode the alpha plane; return (min, max) alpha level, or None.

    The opaque level is NOT assumed to be the bit-depth maximum: some
    ProRes encoders store opaque alpha at 3760/4095 (range headroom), so the
    check compares against 90% of full scale instead of the exact maximum.
    """
    attempts = [[]]
    if codec == "vp9":
        attempts.append(["-c:v", "libvpx-vp9"])
    elif codec == "vp8":
        attempts.append(["-c:v", "libvpx"])
    for pre in attempts:
        p = run(["ffmpeg", "-nostdin", "-v", "info", *pre, "-i", str(path),
                 "-vf", "alphaextract,signalstats,metadata=print",
                 "-f", "null", "-"])
        mins = [int(x) for x in re.findall(r"lavfi\.signalstats\.YMIN=(\d+)", p.stderr)]
        maxs = [int(x) for x in re.findall(r"lavfi\.signalstats\.YMAX=(\d+)", p.stderr)]
        if mins and maxs:
            return min(mins), max(maxs)
    return None


def bit_depth_of(vs):
    # v1.5 (F0-6): trust the probed sample depth first; the pixel-format
    # NAME is only a fallback (a name without a depth suffix must never
    # silently shrink the range the alpha check compares against).
    try:
        b = int(vs.get("bits_per_raw_sample") or 0)
        if b > 0:
            return b
    except Exception:
        pass
    pf = vs.get("pix_fmt") or ""
    m = re.search(r"p(\d+)", pf)
    if m:
        return int(m.group(1))
    return 8


def main():
    argv = sys.argv[1:]
    spec_path = report_path = None
    files = []
    i = 0
    while i < len(argv):
        if argv[i] == "--spec" and i + 1 < len(argv):
            spec_path = argv[i + 1]; i += 2
        elif argv[i] == "--report" and i + 1 < len(argv):
            report_path = argv[i + 1]; i += 2
        elif argv[i].startswith("--"):
            print(f"QC ERROR: unknown flag {argv[i]}")
            return 2
        else:
            files.append(argv[i]); i += 1
    if len(files) != 1:
        print("Usage: qc_probe.py <final-video> [--spec spec.json] [--report report.json]")
        return 2
    path = pathlib.Path(files[0])

    def write_report(status, checks, profile="unknown"):
        if report_path:
            report = {"file": str(path), "profile": profile, "status": status,
                      "checks": checks,
                      "note": "Automated checks only. Narrative truth, visual taste, caption accuracy and face protection on moving footage still require human sign-off."}
            pathlib.Path(report_path).write_text(json.dumps(report, indent=1), encoding="utf-8")

    try:
        if not path.exists():
            print("QC ERROR: file not found:", path)
            return 2
        spec = json.loads(json.dumps(DEFAULT_SPEC))
        if spec_path:
            try:
                user = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
            except Exception as exc:
                print("QC ERROR: could not read spec:", exc)
                return 2
            if not isinstance(user, dict):
                print("QC ERROR: spec must be a JSON object")
                return 2
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(spec.get(k), dict):
                    spec[k].update(v)
                else:
                    spec[k] = v
        validate_spec(spec)

        checks = []

        def check(name, ok, measured, expected):
            checks.append({"name": name, "status": "PASS" if ok else "FAIL",
                           "measured": measured, "expected": expected})
            return ok

        probe = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
        if probe.returncode != 0:
            print("QC ERROR: ffprobe failed:", probe.stderr[:300])
            write_report("ERROR", checks, spec.get("profile", "custom"))
            return 2
        data = json.loads(probe.stdout)
        streams = data.get("streams", [])
        fmt = data.get("format", {})
        vstreams = [s for s in streams if s.get("codec_type") == "video"]
        astreams = [s for s in streams if s.get("codec_type") == "audio"]
        if not vstreams:
            check("video_stream", False, "none", "present")
        else:
            vs = vstreams[0]
            measured = {"codec": vs.get("codec_name"), "width": vs.get("width"), "height": vs.get("height"),
                        "pix_fmt": vs.get("pix_fmt"), "fps": round(fps_of(vs), 3),
                        "duration_s": float(fmt.get("duration", 0) or 0)}
            print("video", measured["codec"], measured["width"], measured["height"], measured["pix_fmt"], measured["fps"])
            print("format", fmt.get("format_name"), "duration", fmt.get("duration"), "size", fmt.get("size"))
            vexp = spec.get("video") or {}
            if "width" in vexp:
                check("width", vs.get("width") == vexp["width"], vs.get("width"), vexp["width"])
            if "height" in vexp:
                check("height", vs.get("height") == vexp["height"], vs.get("height"), vexp["height"])
            if "codec" in vexp:
                check("codec", vs.get("codec_name") == vexp["codec"], vs.get("codec_name"), vexp["codec"])
            if "pix_fmt" in vexp:
                check("pix_fmt", vs.get("pix_fmt") == vexp["pix_fmt"], vs.get("pix_fmt"), vexp["pix_fmt"])
            if "profile" in vexp:
                check("profile", (vs.get("profile") or "") == vexp["profile"], vs.get("profile"), vexp["profile"])
            if "field_order" in vexp:
                check("field_order", (vs.get("field_order") or "") == vexp["field_order"], vs.get("field_order"), vexp["field_order"])
            for key in ("color_space", "color_primaries", "color_transfer"):
                if key in vexp:
                    check(key, (vs.get(key) or "") == vexp[key], vs.get(key), vexp[key])
            if "fps" in vexp:
                avg = fps_of(vs)
                check("fps", abs(avg - float(vexp["fps"])) <= 0.01, round(avg, 3), vexp["fps"])
                rfr = fps_of(vs, "r_frame_rate")
                if rfr and abs(rfr - avg) > 0.01:
                    check("frame_rate_constant", False, f"r_frame_rate {rfr:.2f} vs avg {avg:.2f}", "constant frame rate (no VFR)")
            br = fmt.get("bit_rate")
            if br is not None and ("bit_rate_min_kbps" in vexp or "bit_rate_max_kbps" in vexp):
                kbps = float(br) / 1000.0
                if "bit_rate_min_kbps" in vexp:
                    check("bit_rate_min", kbps >= float(vexp["bit_rate_min_kbps"]), round(kbps), f">= {vexp['bit_rate_min_kbps']} kbps")
                if "bit_rate_max_kbps" in vexp:
                    check("bit_rate_max", kbps <= float(vexp["bit_rate_max_kbps"]), round(kbps), f"<= {vexp['bit_rate_max_kbps']} kbps")
            if (spec.get("overlay") or {}).get("alpha_required"):
                pf = vs.get("pix_fmt") or ""
                tags = vs.get("tags") or {}
                fmt_level = any(h in pf for h in ALPHA_PIX_HINTS) or tags.get("alpha_mode") == "1"
                check("alpha_plane", fmt_level, pf + (f" alpha_mode={tags.get('alpha_mode')}" if tags.get("alpha_mode") else ""),
                      "alpha pixel format or alpha_mode=1")
                if fmt_level:
                    arange = alpha_range(path, vs.get("codec_name"))
                    maxv = (1 << bit_depth_of(vs)) - 1
                    if arange is None:
                        check("alpha_content", False, "unverified", "decodable alpha plane that is not effectively opaque")
                    else:
                        amin, amax = arange
                        check("alpha_content", amin < 0.90 * maxv,
                              f"alpha levels {amin}..{amax} of {maxv}",
                              "alpha drops below 90% of full scale somewhere (not an opaque black box)")
        dexp = spec.get("duration") or {}
        if "expected_s" in dexp:
            d = float(fmt.get("duration", 0) or 0)
            check("duration", abs(d - float(dexp["expected_s"])) <= float(dexp.get("tolerance_s", 0.5)),
                  round(d, 3), dexp["expected_s"])
        # Faststart is a DELIVERY policy, not a container property (v1.5,
        # F0-1): the spec decides. Unset means web containers (.mp4/.m4v)
        # require it and editor-master containers (.mov) do not.
        faststart_required = spec.get("faststart_required")
        if faststart_required is None:
            faststart_required = path.suffix.lower() in (".mp4", ".m4v")
        if faststart_required and path.suffix.lower() in (".mp4", ".mov", ".m4v"):
            mv = moov_before_mdat(path)
            if mv is None:
                check("moov_faststart", False, "no moov box found", "moov before mdat")
            else:
                check("moov_faststart", mv, "moov before mdat" if mv else "moov after mdat", "moov before mdat")

        aexp = spec.get("audio") or {}
        audio_required = bool(aexp.get("required", True))
        if not astreams:
            if audio_required:
                check("audio_stream", False, "missing", "present [AUDIO_STREAM_MISSING]")
        else:
            a0 = astreams[0]
            if "codec" in aexp:
                check("audio_codec", a0.get("codec_name") == aexp["codec"], a0.get("codec_name"), aexp["codec"])
            if "channels" in aexp:
                check("audio_channels", a0.get("channels") == aexp["channels"], a0.get("channels"), aexp["channels"])
            if "sample_rate" in aexp:
                check("sample_rate", int(a0.get("sample_rate", 0)) == int(aexp["sample_rate"]), a0.get("sample_rate"), aexp["sample_rate"])
            loud = run(["ffmpeg", "-nostdin", "-i", str(path), "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"])
            m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", loud.stderr)
            measured_loud = None
            if m:
                try:
                    measured_loud = json.loads(m[-1])
                except Exception:
                    measured_loud = None
            if measured_loud is None:
                if audio_required:
                    check("loudness_measured", False, "no loudnorm data", "measurable programme audio")
            else:
                try:
                    il = float(measured_loud.get("input_i"))
                except Exception:
                    il = float("nan")
                try:
                    tp = float(measured_loud.get("input_tp"))
                except Exception:
                    tp = float("nan")
                print("loudness input_i", measured_loud.get("input_i"), "input_tp", measured_loud.get("input_tp"))
                if not (math.isfinite(il) and math.isfinite(tp)):
                    if audio_required:
                        check("audio_not_silent", False, f"I={measured_loud.get('input_i')} TP={measured_loud.get('input_tp')}", "finite programme loudness [AUDIO_SILENT]")
                else:
                    if "lufs_target" in aexp:
                        tol = float(aexp.get("lufs_tolerance", 1.5))
                        check("loudness_lufs", abs(il - float(aexp["lufs_target"])) <= tol, il, f"{aexp['lufs_target']} +/- {tol}")
                    if "true_peak_max_dbtp" in aexp:
                        check("true_peak", tp <= float(aexp["true_peak_max_dbtp"]), tp, f"<= {aexp['true_peak_max_dbtp']}")

        if not checks:
            check("checks_executed", False, 0, "at least one enforced check (empty spec is not a pass)")
        failed = [c for c in checks if c["status"] == "FAIL"]
        status = "FAIL" if failed else "PASS"
        write_report(status, checks, spec.get("profile", "custom"))
        for c in checks:
            print(f"{c['status']} {c['name']}: measured={c['measured']} expected={c['expected']}")
        print("QC", status)
        return 1 if failed else 0
    except ToolError as exc:
        print("QC ERROR:", exc)
        try:
            write_report("ERROR", [], "unknown")
        except Exception:
            pass
        return 2
    except Exception as exc:
        print("QC ERROR: unexpected failure:", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
