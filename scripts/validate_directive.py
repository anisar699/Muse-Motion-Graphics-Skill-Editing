#!/usr/bin/env python3
"""Muse Motion directive validator v1.1.

Two stages:
  strict (default)  - schema gate + render-ready gate (approval granted,
                      source media exists and probes, geometry rules).
  --draft           - schema gate only. A draft PASS is never render permission.

Exit codes: 0 valid, 1 invalid (handled, no traceback), 2 tool error.
Errors print as INVALID plus one line per error with a stable rule code.
"""
import json, math, subprocess, sys, pathlib

TREATMENTS = {"CLEAN_PRESENTER","OVERLAY_CARD","FULLSCREEN_MOTION","PRESENTER_INSET",
              "SELECTIVE_TEXT","TRANSITION","KINETIC_TYPE","DATA_SCENE","CALLOUT",
              "LOWER_THIRD","TITLE","END_CARD"}
ROLES = {"hook","context","problem","promise","reveal","definition","process",
         "proof","reassurance","transition","cta"}
TRANSITION_TOKENS = {"hard-cut","fade","fade-up","fade-rise","spring-pop","slide-fade",
                     "slide-up","slide-from-right","slide-from-top","slide-from-bottom",
                     "wipe-from-right","wipe-from-left","wipe-right","dissolve","zoom-punch",
                     "whip-pan","fade-to-endcard","none"}
LAYOUT_REQUIRED = TREATMENTS - {"CLEAN_PRESENTER","TRANSITION"}
NO_COLLISION = {"FULLSCREEN_MOTION","PRESENTER_INSET"}  # these legitimately cover the canvas
OVERLAP_LIMIT = 0.50  # fail when overlap >= 50% of the layout area OR >= 50% of the protected area

def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def reject_constant(x):
    raise ValueError(f"non-finite JSON value {x} is not allowed")

def rect_ok(r):
    return (isinstance(r, dict) and is_num(r.get("x")) and is_num(r.get("y"))
            and is_num(r.get("width")) and is_num(r.get("height"))
            and r["width"] > 0 and r["height"] > 0)

def overlap_area(a, b):
    x = max(0, min(a["x"]+a["width"], b["x"]+b["width"]) - max(a["x"], b["x"]))
    y = max(0, min(a["y"]+a["height"], b["y"]+b["height"]) - max(a["y"], b["y"]))
    return x * y

def probe_duration(path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-show_entries","stream=codec_type","-of","json", str(path)],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        return None, False
    d = json.loads(r.stdout)
    dur = float(d.get("format", {}).get("duration", 0) or 0)
    has_video = any(s.get("codec_type") == "video" for s in d.get("streams", []))
    return dur, has_video

def validate(data, draft):
    errors = []
    E = lambda code, msg: errors.append(f"[{code}] {msg}")
    if not isinstance(data, dict):
        return ["[SCHEMA] top level must be a JSON object"]
    if data.get("version") != 1:
        E("SCHEMA", "version must be 1")
    if not isinstance(data.get("project"), str) or not data["project"].strip():
        E("SCHEMA", "project must be a non-empty string")

    fmt = data.get("format")
    cw = ch = None
    if not isinstance(fmt, dict):
        E("FORMAT", "format object is required")
    else:
        w, h, fps, asp = fmt.get("width"), fmt.get("height"), fmt.get("fps"), fmt.get("aspect")
        if not (isinstance(w, int) and not isinstance(w, bool) and w > 0): E("FORMAT", "format.width must be a positive integer")
        if not (isinstance(h, int) and not isinstance(h, bool) and h > 0): E("FORMAT", "format.height must be a positive integer")
        if not (is_num(fps) and fps > 0): E("FORMAT", "format.fps must be a finite positive number")
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            cw, ch = w, h
            if asp is not None:
                ok = isinstance(asp, str) and ":" in asp
                if ok:
                    try:
                        aw, ah = (float(p) for p in asp.split(":", 1))
                        ok = aw > 0 and ah > 0 and abs((w / h) - (aw / ah)) < 0.02
                    except Exception:
                        ok = False
                if not ok: E("FORMAT", f"format.aspect {asp!r} is invalid or inconsistent with width and height")

    src = data.get("source")
    dur = None
    if not isinstance(src, dict):
        E("SOURCE", "source object is required")
    else:
        dur = src.get("duration_s")
        if not (is_num(dur) and dur > 0):
            E("SOURCE", "source.duration_s must be a finite positive number"); dur = None
        spath = src.get("path")
        if not draft:
            if not isinstance(spath, str) or not spath.strip():
                E("SOURCE_MISSING", "source.path is required for a render-ready directive")
            else:
                p = pathlib.Path(spath)
                if not p.is_file():
                    E("SOURCE_MISSING", f"source.path does not exist or is not a file: {spath}")
                elif dur:
                    try:
                        pdur, has_video = probe_duration(p)
                        if pdur is None or not has_video:
                            E("SOURCE_PROBE", "source media could not be probed as a video file")
                        elif abs(pdur - dur) > max(0.5, 0.02 * dur):
                            E("SOURCE_DURATION", f"source.duration_s {dur} differs from probed duration {pdur:.2f} beyond tolerance")
                    except Exception as exc:
                        E("SOURCE_PROBE", f"source media probe failed: {exc}")

    appr = data.get("approval")
    if not isinstance(appr, dict):
        E("APPROVAL_NOT_GRANTED", "approval object is required")
    else:
        amb = appr.get("ambiguities")
        if amb is not None and not isinstance(amb, list):
            E("SCHEMA", "approval.ambiguities must be a list")
        if not draft:
            if appr.get("status") != "approved":
                E("APPROVAL_NOT_GRANTED", f"approval.status must be 'approved' for rendering, got {appr.get('status')!r}")
            if amb:
                E("APPROVAL_NOT_GRANTED", "unresolved approval.ambiguities present, rendering must stop")

    protected = data.get("protected_regions") or []
    if not isinstance(protected, list):
        E("SCHEMA", "protected_regions must be a list"); protected = []
    for i, pr in enumerate(protected):
        if not rect_ok(pr):
            E("GEOMETRY", f"protected_regions[{i}] must be a rectangle with finite positive width and height")
        elif cw and (pr["x"] < 0 or pr["y"] < 0 or pr["x"]+pr["width"] > cw or pr["y"]+pr["height"] > ch):
            E("GEOMETRY", f"protected_regions[{i}] lies outside the canvas")

    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        E("SCHEMA", "beats must be a non-empty list")
        return errors
    prev_end = -1.0; ids = set()
    for i, b in enumerate(beats):
        bid = f"beats[{i}]"
        if not isinstance(b, dict):
            E("SCHEMA", f"{bid} must be an object"); continue
        bid = b.get("id") or bid
        if b.get("id") in ids: E("SCHEMA", f"{bid}: duplicate beat id")
        ids.add(b.get("id"))
        s, e = b.get("start"), b.get("end")
        if not (is_num(s) and is_num(e)):
            E("SCHEMA", f"{bid}: start and end must be finite numbers"); continue
        if s < 0 or e <= s: E("TIMING", f"{bid}: require 0 <= start < end")
        if e - s < 0.4: E("HOLD", f"{bid}: beat duration {e-s:.2f}s is below the 0.4s minimum hold")
        if dur and e > dur + 0.05: E("TIMING", f"{bid}: end exceeds source duration")
        if s < prev_end - 0.001: E("TIMING", f"{bid}: beats overlap or are out of order")
        prev_end = max(prev_end, e)
        tr = b.get("treatment")
        if tr not in TREATMENTS: E("TREATMENT", f"{bid}: unknown treatment {tr!r}")
        if b.get("role") not in ROLES: E("ROLE", f"{bid}: unknown role {b.get('role')!r}")
        if tr == "LOWER_THIRD" and e - s < 3.0: E("HOLD", f"{bid}: LOWER_THIRD must hold at least 3.0s")
        for tk in ("transition_in", "transition_out"):
            if tk in b and b[tk] not in TRANSITION_TOKENS:
                E("TRANSITION", f"{bid}: {tk} token {b[tk]!r} is not in the allowed transition set")
        layout = b.get("layout")
        if tr in LAYOUT_REQUIRED:
            if layout is None:
                E("LAYOUT", f"{bid}: layout is required for treatment {tr}")
            elif not rect_ok(layout):
                E("LAYOUT", f"{bid}: layout must be a rectangle with finite positive width and height")
            else:
                if cw and (layout["x"] < 0 or layout["y"] < 0 or layout["x"]+layout["width"] > cw or layout["y"]+layout["height"] > ch):
                    E("LAYOUT", f"{bid}: layout lies outside the canvas (use an explicit overscan field for intentional off-canvas entrances)")
                if tr not in NO_COLLISION and not b.get("allow_protected_overlap"):
                    la = layout["width"] * layout["height"]
                    for pr in protected:
                        if rect_ok(pr):
                            ov = overlap_area(layout, pr)
                            pa = pr["width"] * pr["height"]
                            if ov > 0 and (ov >= OVERLAP_LIMIT * la or ov >= OVERLAP_LIMIT * pa):
                                E("PROTECTED_REGION", f"{bid}: layout overlaps protected region {pr.get('name')!r} by {ov/la*100:.0f}% of layout and {ov/pa*100:.0f}% of the region (limit 50 percent, or set allow_protected_overlap with a documented reason)")
        copy_list = b.get("on_screen_copy")
        if copy_list is not None and not (isinstance(copy_list, list) and all(isinstance(x, str) for x in copy_list)):
            E("SCHEMA", f"{bid}: on_screen_copy must be a list of strings"); copy_list = None
        rs = b.get("reveal_sync")
        if rs is not None:
            if not isinstance(rs, list):
                E("SCHEMA", f"{bid}: reveal_sync must be a list")
            else:
                for r in rs:
                    if not isinstance(r, dict):
                        E("SCHEMA", f"{bid}: reveal_sync entries must be objects"); continue
                    el, t = r.get("element"), r.get("time")
                    if copy_list is not None and el not in copy_list:
                        E("REVEAL_REF", f"{bid}: reveal_sync element {el!r} is not declared in on_screen_copy")
                    if not is_num(t) or t < s or t > e:
                        E("REVEAL_TIMING", f"{bid}: reveal_sync time must be a finite number inside the beat")
    return errors

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    draft = "--draft" in sys.argv
    if len(args) != 1:
        print("Usage: validate_directive.py <editorial-directive.json> [--draft]"); return 2
    path = pathlib.Path(args[0])
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except Exception as exc:
        print("INVALID", path); print("- [PARSE] handled parse error:", exc); return 1
    try:
        errors = validate(data, draft)
    except Exception as exc:
        print("INVALID", path); print("- [INTERNAL] validation failed safely:", exc); return 1
    if errors:
        print("INVALID", path)
        for e in errors: print("-", e)
        return 1
    mode = "VALID (DRAFT - schema only, NOT render permission)" if draft else "VALID"
    print(mode, path)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
