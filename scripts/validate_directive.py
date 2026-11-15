#!/usr/bin/env python3
"""Muse Motion directive validator v1.4.

Two stages:
  strict (default)  - schema gate + render-ready gate (approval granted with a
                      named approver, source media exists and probes, beats
                      inside the probed timeline, protected regions respected).
  --draft           - schema gate only. Prints "VALID (DRAFT - schema only,
                      NOT render permission)".

v1.4 changes: optional top-level "captions" block (mode/language/style/source)
for the caption engine; house styles locked by the owner (en/roman skill-bar,
ur nastaliq-bar) warn on deviation; burned modes require the built
captions.json to exist at the render gate.

v1.2 changes (from the v1.1 developer audit):
  - source.kind: "video" | "audio" | "none" - audio-only (lyric) and
    graphics-only routes can validate; "none" takes its length from
    timeline.duration_s. Presenter treatments require kind "video".
  - Frame-based hold comparisons (a legal 0.4s / 3.0s hold no longer fails on
    floating-point error).
  - Protected regions: fail at >=10% of the protected area or >=50% of the
    layout area, and on ANY overlap of a region flagged critical. An override
    must be the boolean true AND carry a non-empty overlap_reason; every
    override prints a WARN line and is recorded in --report.
  - Key whitelists everywhere (a typo can no longer disable a check), beat id
    required and unique, version must be the integer 1 (booleans rejected),
    layout type-checked for every treatment.
  - reveal_sync requires on_screen_copy; element must be a string.
  - Reading speed: >40 chars/s errors, >20 chars/s warns.
  - Beat bounds use the PROBED duration (tolerance about one frame);
    format.fps must match the source frame rate; canvas must be even-sized;
    aspect tolerance tightened to 0.005.
  - Exit codes: 0 valid, 1 invalid directive, 2 tool error (missing file,
    unknown flag, ffprobe unavailable). Warnings never change the exit code.
  - Relative source.path resolves against the directive's folder.
  - --report PATH writes a machine-readable JSON result.

Usage: validate_directive.py [--draft] [--report PATH] directive.json
"""
import json
import math
import subprocess
import sys
from pathlib import Path

TREATMENTS = {"CLEAN_PRESENTER", "OVERLAY_CARD", "FULLSCREEN_MOTION", "PRESENTER_INSET",
              "SELECTIVE_TEXT", "TRANSITION", "KINETIC_TYPE", "DATA_SCENE", "CALLOUT",
              "LOWER_THIRD", "TITLE", "END_CARD"}
ROLES = {"hook", "context", "problem", "promise", "reveal", "definition", "process",
         "proof", "reassurance", "transition", "cta"}
# v1.1 tokens kept; v1.2 adds slide-from-left, morph, match-cut, flip, clock-wipe
# (AUD-12). workflow-and-directive.md documents which tokens are entrances and
# which are scene transitions.
TRANSITION_TOKENS = {"hard-cut", "fade", "fade-up", "fade-rise", "spring-pop", "slide-fade",
                     "slide-up", "slide-from-left", "slide-from-right", "slide-from-top",
                     "slide-from-bottom", "wipe-from-right", "wipe-from-left", "wipe-right",
                     "dissolve", "zoom-punch", "whip-pan", "fade-to-endcard", "none",
                     "morph", "match-cut", "flip", "clock-wipe"}
LAYOUT_REQUIRED = TREATMENTS - {"CLEAN_PRESENTER", "TRANSITION"}
NO_COLLISION = {"FULLSCREEN_MOTION", "PRESENTER_INSET"}  # these legitimately cover the canvas
PRESENTER_TREATMENTS = {"CLEAN_PRESENTER", "PRESENTER_INSET", "OVERLAY_CARD", "SELECTIVE_TEXT"}
FPS_SET = {24, 25, 30, 48, 50, 60, 120, 23.976, 29.97, 59.94}
CPS_WARN, CPS_FAIL = 20.0, 40.0

TOP_KEYS = {"version", "project", "theme", "format", "source", "timeline",
            "approval", "protected_regions", "beats", "notes", "captions"}
CAPTION_KEYS = {"mode", "language", "style", "source", "highlight"}
CAPTION_HIGHLIGHTS = {"word", "none"}
CAPTION_MODES = {"none", "sidecar", "burned", "both"}
CAPTION_LANGS = {"en", "ur", "roman"}
CAPTION_STYLES = {"skill-bar", "nastaliq-bar", "karaoke"}
CAPTION_HOUSE_STYLE = {"en": "skill-bar", "roman": "skill-bar", "ur": "nastaliq-bar"}
FORMAT_KEYS = {"width", "height", "fps", "aspect"}
SOURCE_KEYS = {"path", "kind", "duration_s"}
TIMELINE_KEYS = {"duration_s"}
APPROVAL_KEYS = {"status", "ambiguities", "approved_by", "approved_at"}
REGION_KEYS = {"name", "x", "y", "width", "height", "critical"}
BEAT_KEYS = {"id", "start", "end", "role", "treatment", "transition_in", "transition_out",
             "on_screen_copy", "layout", "reveal_sync", "allow_protected_overlap",
             "overlap_reason", "entrance_s", "exit_s", "rationale", "spoken_text"}
REVEAL_KEYS = {"element", "time"}


class ToolError(Exception):
    pass


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def reject_constant(x):
    raise ValueError(f"non-finite JSON value {x} is not allowed")


def rect_ok(r):
    return (isinstance(r, dict) and is_num(r.get("x")) and is_num(r.get("y"))
            and is_num(r.get("width")) and is_num(r.get("height"))
            and r["width"] > 0 and r["height"] > 0)


def overlap_area(a, b):
    x = max(0, min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]))
    y = max(0, min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]))
    return x * y


def probe_media(path):
    """Return (duration_s, has_video, has_audio, video_fps) or None."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration:stream=codec_type,avg_frame_rate,r_frame_rate",
                            "-of", "json", str(path)],
                           capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise ToolError("ffprobe is not available on PATH")
    except subprocess.TimeoutExpired:
        raise ToolError("ffprobe timed out")
    if r.returncode != 0:
        return None
    try:
        d = json.loads(r.stdout)
        dur = float(d["format"]["duration"])
    except Exception:
        return None
    streams = d.get("streams") or []
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    fps = None
    for s in streams:
        if s.get("codec_type") == "video":
            for key in ("avg_frame_rate", "r_frame_rate"):
                try:
                    n, dd = (s.get(key) or "").split("/")
                    if float(dd) != 0:
                        fps = float(n) / float(dd)
                        break
                except Exception:
                    continue
        if fps:
            break
    return dur, has_video, has_audio, fps


def validate(data, draft, directive_dir):
    errors, warnings = [], []
    E = lambda code, msg: errors.append(f"[{code}] {msg}")
    W = lambda code, msg: warnings.append(f"[{code}] {msg}")

    def unknown(obj, allowed, where):
        if isinstance(obj, dict):
            for k in obj:
                if k not in allowed:
                    E("SCHEMA", f"{where}: unknown key {k!r}")

    if not isinstance(data, dict):
        return ["[SCHEMA] top level must be a JSON object"], warnings
    unknown(data, TOP_KEYS, "directive")
    if type(data.get("version")) is not int or data.get("version") != 1:
        E("SCHEMA", "version must be the integer 1")
    if not isinstance(data.get("project"), str) or not data["project"].strip():
        E("SCHEMA", "project must be a non-empty string")

    # ---- format ----
    fmt = data.get("format")
    cw = ch = None
    fps = 30.0
    if not isinstance(fmt, dict):
        E("FORMAT", "format object is required")
    else:
        unknown(fmt, FORMAT_KEYS, "format")
        w, h, fa, asp = fmt.get("width"), fmt.get("height"), fmt.get("fps"), fmt.get("aspect")
        if not (isinstance(w, int) and not isinstance(w, bool) and w > 0):
            E("FORMAT", "format.width must be a positive integer")
        if not (isinstance(h, int) and not isinstance(h, bool) and h > 0):
            E("FORMAT", "format.height must be a positive integer")
        if isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0:
            cw, ch = w, h
            if w % 2 or h % 2:
                E("FORMAT", "format.width/height must be even (yuv420 delivery)")
            if asp is not None:
                ok = isinstance(asp, str) and ":" in asp
                if ok:
                    try:
                        aw, ah = (float(p) for p in asp.split(":", 1))
                        ok = aw > 0 and ah > 0 and abs((w / h) - (aw / ah)) <= 0.005
                    except Exception:
                        ok = False
                if not ok:
                    E("FORMAT", f"format.aspect {asp!r} is invalid or inconsistent with width and height")
        if is_num(fa) and fa > 0:
            fps = float(fa)
            if not any(abs(fps - f) < 0.01 for f in FPS_SET):
                E("FORMAT", f"format.fps {fps} is not a standard frame rate")
        else:
            E("FORMAT", "format.fps must be a finite positive number")

    # ---- source / timeline ----
    src = data.get("source")
    timeline = data.get("timeline")
    if timeline is not None:
        if not isinstance(timeline, dict):
            E("SCHEMA", "timeline must be an object")
            timeline = None
        else:
            unknown(timeline, TIMELINE_KEYS, "timeline")
    kind, src_path, declared_dur = "video", None, None
    if src is None:
        kind = "none"
    elif not isinstance(src, dict):
        E("SOURCE", "source must be an object")
        src = None
    else:
        unknown(src, SOURCE_KEYS, "source")
        kind = src.get("kind", "video")
        if kind not in ("video", "audio", "none"):
            E("SOURCE", f"source.kind {kind!r} must be 'video', 'audio' or 'none'")
            kind = "video"
        if is_num(src.get("duration_s")) and src["duration_s"] > 0:
            declared_dur = float(src["duration_s"])
        elif kind in ("video", "audio"):
            E("SOURCE", "source.duration_s must be a finite positive number")
        if kind in ("video", "audio"):
            sp = src.get("path")
            if not isinstance(sp, str) or not sp.strip():
                E("SOURCE_MISSING", "source.path is required for kind video/audio")
            else:
                p = Path(sp)
                src_path = p if p.is_absolute() else (directive_dir / p)
    if kind == "none":
        tl = timeline.get("duration_s") if isinstance(timeline, dict) else None
        if is_num(tl) and tl > 0:
            declared_dur = float(tl)
        elif not draft:
            E("SOURCE", "graphics-only route requires timeline.duration_s")

    # ---- approval ----
    appr = data.get("approval")
    if not isinstance(appr, dict):
        E("APPROVAL_NOT_GRANTED", "approval object is required")
    else:
        unknown(appr, APPROVAL_KEYS, "approval")
        amb = appr.get("ambiguities")
        if amb is not None and not isinstance(amb, list):
            E("SCHEMA", "approval.ambiguities must be a list")
        if not draft:
            if appr.get("status") != "approved":
                E("APPROVAL_NOT_GRANTED", f"approval.status must be 'approved' for rendering, got {appr.get('status')!r}")
            if amb:
                E("APPROVAL_NOT_GRANTED", "unresolved approval.ambiguities present, rendering must stop")
            if not isinstance(appr.get("approved_by"), str) or not appr["approved_by"].strip():
                E("APPROVAL_NOT_GRANTED", "approval.approved_by (who approved) is required for rendering")
            if not appr.get("approved_at"):
                W("APPROVAL", "approval.approved_at is not recorded")

    # ---- captions (v1.4, optional block) ----
    caps = data.get("captions")
    if caps is not None:
        if not isinstance(caps, dict):
            E("SCHEMA", "captions must be an object")
        else:
            unknown(caps, CAPTION_KEYS, "captions")
            cmode = caps.get("mode")
            if cmode not in CAPTION_MODES:
                E("CAPTIONS", f"captions.mode must be one of {sorted(CAPTION_MODES)}, got {cmode!r}")
            clang = caps.get("language")
            if cmode in {"sidecar", "burned", "both"} and clang not in CAPTION_LANGS:
                E("CAPTIONS", f"captions.language must be one of {sorted(CAPTION_LANGS)} when captions are on, got {clang!r}")
            cstyle = caps.get("style")
            if cstyle is not None and cstyle not in CAPTION_STYLES:
                E("CAPTIONS", f"captions.style must be one of {sorted(CAPTION_STYLES)}, got {cstyle!r}")
            chigh = caps.get("highlight")
            if chigh is not None and chigh not in CAPTION_HIGHLIGHTS:
                E("CAPTIONS", f"captions.highlight must be one of {sorted(CAPTION_HIGHLIGHTS)}, got {chigh!r}")
            if clang in CAPTION_HOUSE_STYLE and cstyle is not None and cstyle != CAPTION_HOUSE_STYLE[clang]:
                W("CAPTIONS", f"captions.style {cstyle!r} deviates from the locked house style {CAPTION_HOUSE_STYLE[clang]!r} for language {clang!r} (owner decision 2026-11-15)")
            if not draft and cmode in {"burned", "both"}:
                csrc = caps.get("source")
                if not isinstance(csrc, str) or not csrc.strip():
                    E("CAPTIONS", "captions.source (the captions.json built by build_captions.py) is required for burned captions at render time")
                else:
                    cpath = Path(csrc)
                    if not cpath.is_absolute():
                        cpath = (directive_dir / cpath)
                    if not cpath.is_file():
                        E("CAPTIONS", f"captions.source not found: {csrc}")
                    else:
                        # Content match (v1.7, audit H-01): existence is
                        # not enough - a stale or wrong-language build
                        # must not reach the render. Compare the built
                        # captions' own metadata against this directive.
                        try:
                            cmeta = json.loads(cpath.read_text(encoding="utf-8"))
                        except Exception:
                            cmeta = None
                            E("CAPTIONS", f"captions.source is not valid JSON: {csrc}")
                        if isinstance(cmeta, dict):
                            if clang and cmeta.get("language") != clang:
                                E("CAPTIONS", f"captions.source language {cmeta.get('language')!r} does not match captions.language {clang!r} - stale or wrong build")
                            if cstyle and cmeta.get("style") != cstyle:
                                E("CAPTIONS", f"captions.source style {cmeta.get('style')!r} does not match captions.style {cstyle!r} - stale or wrong build")
                            if chigh and bool(cmeta.get("word_highlight")) != (chigh == "word"):
                                E("CAPTIONS", f"captions.source word_highlight {cmeta.get('word_highlight')!r} does not match captions.highlight {chigh!r}")
                            ccanvas = cmeta.get("canvas") or {}
                            fmt = data.get("format") or {}
                            if ccanvas.get("width") != fmt.get("width") or ccanvas.get("height") != fmt.get("height"):
                                E("CAPTIONS", f"captions.source canvas {ccanvas.get('width')}x{ccanvas.get('height')} does not match format {fmt.get('width')}x{fmt.get('height')}")

    # ---- caption-zone placement (v1.6, owner rule 2026-11-15) ----
    # With burned/both captions, heading and fact cards parked in the
    # bottom zone crowd the caption band and read as part of it; they
    # belong in the top zone, the way a title card sits. Warning only -
    # a deliberate lower-third design can still be approved knowingly.
    if isinstance(caps, dict) and caps.get("mode") in {"burned", "both"}:
        fmt_h = (data.get("format") or {}).get("height")
        if isinstance(fmt_h, (int, float)) and fmt_h > 0:
            zone_top = fmt_h - round(0.26 * fmt_h)
            for b in data.get("beats") or []:
                if not isinstance(b, dict):
                    continue
                lay = b.get("layout") or {}
                y, h = lay.get("y"), lay.get("height")
                if isinstance(y, (int, float)) and isinstance(h, (int, float)) \
                        and y + h > zone_top:
                    W("PLACEMENT", f"beat {b.get('id')!r}: layout bottom {y + h:.0f} enters the caption zone (bottom 26% of frame, from y={zone_top}) while captions are {caps.get('mode')} - heading/fact cards belong in the top zone, clear of the caption band (owner rule 2026-11-15)")

    # ---- protected regions ----
    protected = data.get("protected_regions") or []
    if not isinstance(protected, list):
        E("SCHEMA", "protected_regions must be a list")
        protected = []
    for i, pr in enumerate(protected):
        if isinstance(pr, dict):
            unknown(pr, REGION_KEYS, f"protected_regions[{i}]")
            if "critical" in pr and not isinstance(pr["critical"], bool):
                E("SCHEMA", f"protected_regions[{i}].critical must be a boolean")
        if not rect_ok(pr):
            E("GEOMETRY", f"protected_regions[{i}] must be a rectangle with finite positive width and height")
        elif cw and (pr["x"] < 0 or pr["y"] < 0 or pr["x"] + pr["width"] > cw or pr["y"] + pr["height"] > ch):
            E("GEOMETRY", f"protected_regions[{i}] lies outside the canvas")

    # ---- beats ----
    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        E("SCHEMA", "beats must be a non-empty list")
        return errors, warnings
    prev_end, ids, spans = -1.0, set(), []
    for i, b in enumerate(beats):
        bid = f"beats[{i}]"
        if not isinstance(b, dict):
            E("SCHEMA", f"{bid} must be an object")
            continue
        unknown(b, BEAT_KEYS, bid)
        if not isinstance(b.get("id"), str) or not b["id"].strip():
            E("SCHEMA", f"{bid}: a non-empty string id is required")
        else:
            bid = b["id"]
            if bid in ids:
                E("SCHEMA", f"{bid}: duplicate beat id")
            ids.add(bid)
        s, e = b.get("start"), b.get("end")
        if not (is_num(s) and is_num(e)):
            E("SCHEMA", f"{bid}: start and end must be finite numbers")
            continue
        s, e = float(s), float(e)
        if s < 0 or e <= s:
            E("TIMING", f"{bid}: require 0 <= start < end")
            continue
        spans.append((s, e, bid))
        dur_frames = round((e - s) * fps)
        if dur_frames < round(0.4 * fps):
            E("HOLD", f"{bid}: beat duration {e - s:.2f}s is below the 0.4s minimum hold")
        if s < prev_end - 0.001:
            E("TIMING", f"{bid}: beats overlap or are out of order")
        prev_end = max(prev_end, e)
        tr = b.get("treatment")
        if not isinstance(tr, str) or tr not in TREATMENTS:
            E("TREATMENT", f"{bid}: unknown treatment {tr!r}")
            tr = None
        if not isinstance(b.get("role"), str) or b.get("role") not in ROLES:
            E("ROLE", f"{bid}: unknown role {b.get('role')!r}")
        if tr == "LOWER_THIRD" and dur_frames < round(3.0 * fps):
            E("HOLD", f"{bid}: LOWER_THIRD must hold at least 3.0s")
        for tk in ("transition_in", "transition_out"):
            if tk in b and (not isinstance(b[tk], str) or b[tk] not in TRANSITION_TOKENS):
                E("TRANSITION", f"{bid}: {tk} token {b[tk]!r} is not in the allowed transition set")
        for dk in ("entrance_s", "exit_s"):
            if dk in b and not (is_num(b[dk]) and b[dk] >= 0):
                E("SCHEMA", f"{bid}: {dk} must be a non-negative number")
        if is_num(b.get("entrance_s")) and is_num(b.get("exit_s")):
            if (e - s) < float(b["entrance_s"]) + float(b["exit_s"]) + 0.4 - 1e-9:
                E("HOLD", f"{bid}: beat is shorter than entrance + exit + minimum hold")
        if tr in PRESENTER_TREATMENTS and kind != "video":
            E("SOURCE_KIND", f"{bid}: treatment {tr} requires source.kind 'video', got {kind!r}")
        # layout: type-checked for every treatment
        layout = b.get("layout")
        if "layout" in b and layout is not None and not rect_ok(layout):
            E("LAYOUT", f"{bid}: layout must be null or a rectangle with finite positive width and height")
            layout = None
        if tr in LAYOUT_REQUIRED and layout is None:
            E("LAYOUT", f"{bid}: layout is required for treatment {tr}")
        if rect_ok(layout):
            if cw and (layout["x"] < 0 or layout["y"] < 0
                       or layout["x"] + layout["width"] > cw or layout["y"] + layout["height"] > ch):
                E("LAYOUT", f"{bid}: layout lies outside the canvas (declare an intentional overscan in the beat rationale instead)")
            if tr not in NO_COLLISION:
                override = b.get("allow_protected_overlap")
                reason = b.get("overlap_reason")
                override_ok = override is True and isinstance(reason, str) and bool(reason.strip())
                if override is True and not override_ok:
                    E("OVERRIDE", f"{bid}: allow_protected_overlap requires a non-empty overlap_reason string")
                la = layout["width"] * layout["height"]
                for pr in protected:
                    if not rect_ok(pr):
                        continue
                    ov = overlap_area(layout, pr)
                    if ov <= 0:
                        continue
                    pa = pr["width"] * pr["height"]
                    if override_ok:
                        W("PROTECTED_OVERRIDE", f"{bid}: overlaps protected region {pr.get('name')!r} by {ov / pa * 100:.0f}% of the region; reason: {reason}")
                    elif pr.get("critical") is True or ov >= 0.10 * pa or ov >= 0.50 * la:
                        E("PROTECTED_REGION", f"{bid}: layout overlaps protected region {pr.get('name')!r} by {ov / la * 100:.0f}% of layout and {ov / pa * 100:.0f}% of the region (limits: 10% of the region, 50% of the layout, any overlap on critical regions; or set allow_protected_overlap to true with an overlap_reason)")
        # copy + reading speed
        copy_list = b.get("on_screen_copy")
        if copy_list is not None and not (isinstance(copy_list, list) and all(isinstance(x, str) for x in copy_list)):
            E("SCHEMA", f"{bid}: on_screen_copy must be a list of strings")
            copy_list = None
        if copy_list:
            cps = sum(len(c) for c in copy_list) / (e - s)
            if cps > CPS_FAIL:
                E("READABILITY", f"{bid}: on-screen copy runs at {cps:.0f} chars/s (limit {CPS_FAIL:.0f})")
            elif cps > CPS_WARN:
                W("READABILITY", f"{bid}: on-screen copy runs at {cps:.0f} chars/s (caption guide is {CPS_WARN:.0f})")
        # reveal sync
        rs = b.get("reveal_sync")
        if rs is not None:
            if not isinstance(rs, list):
                E("SCHEMA", f"{bid}: reveal_sync must be a list")
            else:
                if rs and not copy_list:
                    E("REVEAL_REF", f"{bid}: reveal_sync requires on_screen_copy declaring each element")
                for r in rs:
                    if not isinstance(r, dict):
                        E("SCHEMA", f"{bid}: reveal_sync entries must be objects")
                        continue
                    unknown(r, REVEAL_KEYS, f"{bid}.reveal_sync")
                    el, t = r.get("element"), r.get("time")
                    if not isinstance(el, str):
                        E("REVEAL_REF", f"{bid}: reveal_sync element must be a string")
                    elif copy_list and el not in copy_list:
                        E("REVEAL_REF", f"{bid}: reveal_sync element {el!r} is not declared in on_screen_copy")
                    if not is_num(t) or t < s or t > e:
                        E("REVEAL_TIMING", f"{bid}: reveal_sync time must be a finite number inside the beat")
    spans.sort()
    for (s1, e1, id1), (s2, e2, id2) in zip(spans, spans[1:]):
        if s2 - e1 > 0.5:
            W("GAP", f"{s2 - e1:.1f}s gap between beats {id1!r} and {id2!r} has no declared treatment")
    if draft:
        if declared_dur is not None:
            for (s, e, bid) in spans:
                if e > declared_dur + 0.05:
                    E("TIMING", f"{bid}: end exceeds the declared timeline duration")
        return errors, warnings

    # ---- render-ready: probe + bounds against the real timeline ----
    effective = declared_dur
    if kind in ("video", "audio"):
        if src_path is not None:
            if not src_path.is_file():
                E("SOURCE_MISSING", f"source.path does not exist or is not a file: {src_path}")
            else:
                probed = probe_media(src_path)
                if probed is None:
                    E("SOURCE_PROBE", "source media could not be probed as a media file")
                else:
                    pdur, has_v, has_a, pfps = probed
                    if kind == "video" and not has_v:
                        E("SOURCE_PROBE", "source has no video stream but source.kind is 'video'")
                    if kind == "audio" and not has_a:
                        E("SOURCE_PROBE", "source has no audio stream but source.kind is 'audio'")
                    effective = pdur
                    if declared_dur is not None and abs(pdur - declared_dur) > max(1.0 / fps, 0.05):
                        E("SOURCE_DURATION", f"source.duration_s {declared_dur} differs from probed duration {pdur:.2f} beyond one frame")
                    if kind == "video" and pfps and abs(pfps - fps) > 0.01:
                        E("FORMAT_FPS", f"format.fps {fps} does not match the source frame rate {pfps:.2f}")
    if effective is not None:
        tol = 1.0 / fps + 1e-6
        for (s, e, bid) in spans:
            if e > effective + tol:
                E("TIMING", f"{bid}: end exceeds the timeline duration {effective:.2f}s")
    return errors, warnings


def main(argv):
    draft, report_path, positional = False, None, []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--draft":
            draft = True
        elif a == "--report":
            i += 1
            if i >= len(argv):
                print("TOOL ERROR: --report needs a path")
                return 2
            report_path = argv[i]
        elif a.startswith("--"):
            print(f"TOOL ERROR: unknown flag {a}")
            return 2
        else:
            positional.append(a)
        i += 1
    if len(positional) != 1:
        print("Usage: validate_directive.py <editorial-directive.json> [--draft] [--report PATH]")
        return 2
    path = Path(positional[0])
    if not path.is_file():
        print(f"TOOL ERROR: directive file not found: {path}")
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except Exception as exc:
        print("INVALID", path)
        print("- [PARSE] handled parse error:", exc)
        return 1
    try:
        errors, warnings = validate(data, draft, path.resolve().parent)
    except ToolError as exc:
        print(f"TOOL ERROR: {exc}")
        return 2
    except Exception as exc:
        print("TOOL ERROR: unexpected validator failure:", exc)
        return 2
    if report_path:
        try:
            Path(report_path).write_text(json.dumps(
                {"directive": str(path), "mode": "draft" if draft else "strict",
                 "status": "INVALID" if errors else "VALID",
                 "errors": errors, "warnings": warnings}, indent=1))
        except Exception as exc:
            print(f"TOOL ERROR: could not write report: {exc}")
            return 2
    if errors:
        print("INVALID", path)
        for e in errors:
            print("-", e)
        return 1
    mode = "VALID (DRAFT - schema only, NOT render permission)" if draft else "VALID"
    print(mode, path)
    for w in warnings:
        print("WARN", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
