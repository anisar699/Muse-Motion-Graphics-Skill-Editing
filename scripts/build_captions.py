#!/usr/bin/env python3
"""Muse Motion caption engine (v1.4).

Builds burned-in caption assets and an SRT sidecar from a word-timestamped
transcript (the transcript.json written by transcribe.py), in the house
styles locked by the owner on 2026-11-15:

  en    -> "skill-bar"    (charcoal bar, white bold text, amber underline)
  roman -> "skill-bar"    (Roman Urdu, transliterated from an Urdu transcript)
  ur    -> "nastaliq-bar" (same bar, Noto Nastaliq Urdu, RTL)

Both bar styles include word-by-word highlighting (owner decision
2026-11-15): the word being spoken turns amber inside the bar, rendered
as one PNG state per word. --no-highlight renders one static PNG per cue.

Language honesty rules:
  - en captions come straight from an English transcript.
  - ur captions come straight from an Urdu transcript.
  - roman captions are a TRANSLITERATION of an Urdu transcript, using
    references/roman-urdu-dictionary.json plus a character fallback. The
    tool prints the dictionary coverage; low coverage means a human should
    review spellings. Turning ENGLISH speech into Urdu/Roman captions is
    translation, which this tool deliberately does not fake: transcribe the
    Urdu audio, or supply a reviewed translation as a transcript-shaped
    JSON (segments with start/end/text).

Outputs (in --out-dir):
  captions.json   cue list + metadata (this is the directive captions.source)
  captions.srt    sidecar for YouTube etc.
  layer.ffconcat  concat-demuxer manifest for the overlay input
  pngs/           one full-canvas transparent PNG per cue + gap.png

Burn-in: add the layer as one more input and overlay it LAST (above the
graphics, below nothing else):
  ffmpeg ... -f concat -safe 0 -i layer.ffconcat ...
  ... [base][N:v]overlay=0:0:eof_action=pass [out]

Exit codes: 0 ok, 1 self-check failed, 2 tool error.
"""
import argparse
import json
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
AMBER = (245, 166, 35, 255)
WHITE = (255, 255, 255, 255)
PANEL = (16, 16, 19, 215)
DEFAULT_MAX_CHARS = {"en": 42, "roman": 42, "ur": 34}

CHAR_FALLBACK = {
    "ا": "a", "آ": "aa", "ب": "b", "پ": "p", "ت": "t", "ٹ": "t", "ث": "s",
    "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d", "ڈ": "d", "ذ": "z",
    "ر": "r", "ڑ": "r", "ز": "z", "ژ": "zh", "س": "s", "ش": "sh", "ص": "s",
    "ض": "z", "ط": "t", "ظ": "z", "ع": "a", "غ": "gh", "ف": "f", "ق": "q",
    "ک": "k", "گ": "g", "ل": "l", "م": "m", "ن": "n", "ں": "n", "و": "o",
    "ہ": "a", "ھ": "h", "ی": "i", "ے": "e", "ؤ": "o", "ئ": "i", "ۂ": "a",
    "ٰ": "a", "ء": "", "َ": "", "ِ": "", "ُ": "", "ّ": "", "ْ": "",
    "ً": "", "ٍ": "", "ٌ": "",
}
PUNCT = {"۔": ".", "،": ",", "؟": "?", "؛": ";"}


def transliterate(word, dictionary):
    suffix = ""
    while word and word[-1] in PUNCT:
        suffix = PUNCT[word[-1]] + suffix
        word = word[:-1]
    if word in dictionary:
        return dictionary[word] + suffix, True
    return "".join(CHAR_FALLBACK.get(ch, ch) for ch in word) + suffix, False


def load_words(transcript):
    """Flatten the transcript to a word list, validating the data the
    timing model depends on (v1.7, audit M-08): every word needs numeric
    start/end with end >= start, and the list is time-ordered (sorted
    defensively, and the caller is told). Malformed entries raise
    ValueError - a clean tool error, never a traceback or silent garbage."""
    words = []
    for si, seg in enumerate(transcript.get("segments", [])):
        sw = seg.get("words") or []
        if sw:
            for w in sw:
                t = (w.get("word") or "").strip()
                if not t:
                    continue
                try:
                    st, en = float(w["start"]), float(w["end"])
                except (KeyError, TypeError, ValueError):
                    raise ValueError(
                        f"segment {si}: word {t!r} has missing or non-numeric start/end")
                if en < st - 0.05:
                    raise ValueError(
                        f"segment {si}: word {t!r} ends at {en} before it starts at {st}")
                words.append({"text": t, "start": st, "end": max(en, st)})
        elif seg.get("text"):
            parts = seg["text"].split()
            if parts:
                try:
                    s0, s1 = float(seg["start"]), float(seg["end"])
                except (KeyError, TypeError, ValueError):
                    raise ValueError(f"segment {si}: missing or non-numeric start/end")
                step = (s1 - s0) / len(parts)
                for i, t in enumerate(parts):
                    words.append({"text": t, "start": s0 + i * step,
                                  "end": s0 + (i + 1) * step})
    disordered = any(words[i]["start"] < words[i - 1]["start"] - 0.001
                     for i in range(1, len(words)))
    if disordered:
        words.sort(key=lambda x: x["start"])
    return words, disordered


def build_cues(words, max_chars, max_cps, max_dur=6.5, gap_break=0.6,
               total_duration=None):
    """Caption timing model - ANCHORED to the speech (v1.7, audit C-01):
    words are grouped into blocks at real pauses and into phrase groups
    inside each block, then every cue is timed from ITS OWN words:
    it starts at most 0.3s before its first word (and never before the
    previous cue ends), and it ends no earlier than its last word plus a
    0.2s tail, extended when the reading-speed limit needs more time and
    floored at 0.7s. Cues whose final speed still exceeds max_cps are
    returned in `bursts` and reported, never hidden.

    The pre-v1.7 model tiled each block's window proportionally to cue
    character counts. When char density and speech rate diverged (a few
    characters spoken slowly, then many spoken fast), a cue could appear
    SECONDS before its words were spoken - reproduced at 3.9s early on a
    synthetic fixture and 7.27s on the auditors' fixture. Anchoring makes
    that class of error impossible by construction.

    When total_duration is given, cue ends are clamped to it and words
    starting past it are dropped (audit H-04); the counts come back in
    the third return value so the build can declare them."""
    # 1) blocks
    blocks, cur = [], [words[0]]
    for w in words[1:]:
        if w["start"] - cur[-1]["end"] > gap_break:
            blocks.append(cur)
            cur = []
        cur.append(w)
    blocks.append(cur)

    norm, bursts = [], []
    clamped = dropped = 0
    prev_end = 0.0
    for bi, block in enumerate(blocks):
        # 2) cue groups inside the block. A group may swallow one short
        # trailing word past the char budget (lookahead): short words bind
        # tightly to what precedes them ("night side"), and splitting them
        # off is the classic broken-caption look. Never swallow across a
        # sentence end - a capital that starts a new sentence stays put.
        groups, g = [], []
        swallowed = False
        for w in block:
            if g:
                chars = sum(len(x["text"]) for x in g) + len(g) - 1 + 1 + len(w["text"])
                over = chars > max_chars or w["end"] - g[0]["start"] > max_dur
                if over and not swallowed and len(w["text"]) <= 5 \
                        and chars <= max_chars + 6 \
                        and not g[-1]["text"].rstrip().endswith((".", "!", "?")) \
                        and w["end"] - g[0]["start"] <= max_dur:
                    over = False
                    swallowed = True
                if over:
                    groups.append(g)
                    g = []
                    swallowed = False
            g.append(w)
        if g:
            groups.append(g)
        # 2b) group repairs (user audit 2026-11-15): a one-word tail group
        # flashes on screen ("routine."), and a group ending on a function
        # word splits a phrase ("A city in / space."). Merge orphans into
        # the previous group (two rendered lines allow up to 2x the char
        # budget) and shift trailing function words forward. Repeat until
        # stable. The orphan threshold is relative to the cue budget -
        # an absolute 12 chars misfires at small --max-chars values.
        def glen(gr):
            return sum(len(x["text"]) for x in gr) + len(gr) - 1
        orphan_max = max(6, round(0.29 * max_chars))
        merge_cap = 2 * max_chars
        FUNC = {"the", "a", "an", "in", "on", "of", "to", "for", "with",
                "by", "from", "at", "and", "or", "but", "as", "into",
                "over", "under", "between", "through", "during", "before",
                "after", "per", "via"}
        for _ in range(8):
            changed = False
            for i in range(1, len(groups)):
                if (len(groups[i]) == 1 or glen(groups[i]) <= orphan_max) \
                        and glen(groups[i - 1]) + 1 + glen(groups[i]) <= merge_cap:
                    groups[i - 1] = groups[i - 1] + groups[i]
                    del groups[i]
                    changed = True
                    break
            if changed:
                continue
            for i in range(len(groups) - 1):
                g = groups[i]
                if len(g) > 1 and \
                        g[-1]["text"].strip(".,!?").lower() in FUNC and \
                        glen(groups[i + 1]) + 1 + len(g[-1]["text"]) <= merge_cap:
                    groups[i + 1] = [g[-1]] + groups[i + 1]
                    groups[i] = g[:-1]
                    changed = True
                    break
            if not changed:
                break
        # 3) anchored timing (v1.7): each cue is timed from its own
        # words - see the docstring. Reading-speed extensions can push a
        # cue's end into the following pause (or, in dense speech, push
        # the next cue's start); the final per-cue speed decides bursts.
        for g in groups:
            chars = sum(len(x["text"]) for x in g) + len(g) - 1
            start = max(g[0]["start"] - 0.3, prev_end + 0.04) if norm \
                else max(g[0]["start"] - 0.3, 0.0)
            if total_duration is not None and start >= total_duration - 0.05:
                dropped += 1
                continue
            end = max(g[-1]["end"] + 0.2, start + chars / max_cps, start + 0.7)
            if total_duration is not None and end > total_duration:
                end = total_duration
                clamped += 1
            cue = {"start": round(start, 3), "end": round(end, 3), "words": g}
            if chars / max(end - start, 0.01) > max_cps:
                bursts.append(cue)
            norm.append(cue)
            prev_end = end
    return norm, bursts, {"clamped": clamped, "dropped": dropped}


def srt_time(s):
    h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60); ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript")
    ap.add_argument("--lang", required=True, choices=["en", "ur", "roman"])
    ap.add_argument("--out-dir")
    ap.add_argument("--video", default="1920x1080", help="canvas WxH")
    ap.add_argument("--duration", type=float, help="timeline duration for the layer tail (default: last cue end + 1)")
    ap.add_argument("--max-chars", type=int)
    ap.add_argument("--max-cps", type=float, default=20.0)
    ap.add_argument("--bottom-margin", type=int)
    ap.add_argument("--font-en", help="bold Latin font file (default: platform search, see code)")
    ap.add_argument("--font-ur")
    ap.add_argument("--dictionary", default=str(SKILL / "references" / "roman-urdu-dictionary.json"))
    ap.add_argument("--force", action="store_true", help="skip the transcript-language match check")
    ap.add_argument("--no-highlight", action="store_true",
                    help="disable the word-by-word amber highlight (one static PNG per cue)")
    args = ap.parse_args()

    tpath = Path(args.transcript)
    if not tpath.is_file():
        print(f"build_captions: ERROR transcript not found: {tpath}", file=sys.stderr)
        sys.exit(2)
    try:
        transcript = json.loads(tpath.read_text())
    except Exception as e:
        print(f"build_captions: ERROR transcript is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)
    tlang = (transcript.get("language") or "").lower()
    need = "en" if args.lang == "en" else "ur"
    if not args.force and not tlang.startswith(need):
        print(f"build_captions: ERROR --lang {args.lang} needs a '{need}' transcript, "
              f"this one is '{tlang or 'unknown'}'. For {args.lang} captions of "
              f"{tlang} speech, translation is required first (a human-reviewed step "
              "this tool does not fake). Use transcribe.py --language " + need + " on "
              "matching audio, or pass a reviewed translation in transcript shape.",
              file=sys.stderr)
        sys.exit(2)

    try:
        words, disordered = load_words(transcript)
    except ValueError as e:
        print(f"build_captions: ERROR malformed transcript: {e}", file=sys.stderr)
        sys.exit(2)
    if not words:
        print("build_captions: ERROR transcript has no words/segments", file=sys.stderr)
        sys.exit(2)
    if disordered:
        print("build_captions: NOTE transcript words were out of time order; sorted by start time")
    # Script check (v1.7, audit M-03): the language gate above trusts the
    # transcript's label, and Whisper can mislabel. Cross-check the label
    # against the actual script of the words before building anything.
    if not args.force:
        alpha = [ch for w in words for ch in w["text"] if ch.isalpha()]
        arabic = sum(1 for ch in alpha
                     if "\u0600" <= ch <= "\u06FF" or "\u0750" <= ch <= "\u077F"
                     or "\uFB50" <= ch <= "\uFDFF" or "\uFE70" <= ch <= "\uFEFF")
        share = (arabic / len(alpha)) if alpha else 0.0
        if need == "ur" and share < 0.5:
            print(f"build_captions: ERROR transcript is labelled '{tlang}' but only "
                  f"{share:.0%} of its letters are Arabic script - the label and the "
                  "text disagree (mislabelled transcript?). Fix the transcript or "
                  "pass --force if this is a reviewed exception.", file=sys.stderr)
            sys.exit(2)
        if need == "en" and share > 0.05:
            print(f"build_captions: ERROR transcript is labelled '{tlang}' but "
                  f"{share:.0%} of its letters are Arabic script - the label and the "
                  "text disagree (mislabelled transcript?). Fix the transcript or "
                  "pass --force if this is a reviewed exception.", file=sys.stderr)
            sys.exit(2)

    coverage = None
    if args.lang == "roman":
        try:
            dictionary = json.loads(Path(args.dictionary).read_text(encoding="utf-8"))["words"]
        except Exception as e:
            print(f"build_captions: ERROR cannot read roman dictionary: {e}", file=sys.stderr)
            sys.exit(2)
        hits = 0
        for w in words:
            w["text"], hit = transliterate(w["text"], dictionary)
            hits += hit
        coverage = round(100.0 * hits / len(words), 1)
        # Coverage gate (v1.7, audit M-02): below 60% the output would be
        # mostly character-fallback guesswork - fail loudly instead of
        # passing at any coverage. --force overrides, on the record.
        if coverage < 60 and not args.force:
            print(f"build_captions: ERROR roman dictionary coverage is {coverage}% - "
                  "most words would be transliterated by character fallback. Extend "
                  "references/roman-urdu-dictionary.json, or pass --force to accept "
                  "the spellings anyway.", file=sys.stderr)
            sys.exit(1)

    try:
        W, H = (int(x) for x in args.video.lower().split("x"))
    except Exception:
        print("build_captions: ERROR --video must look like 1920x1080", file=sys.stderr)
        sys.exit(2)

    from PIL import Image, ImageDraw, ImageFont
    rtl = args.lang == "ur"
    if rtl:
        # libraqm check (v1.7, audit L-03): without raqm, Pillow draws
        # Urdu unshaped (letters disconnected) with NO error - refuse
        # loudly instead of shipping broken script.
        from PIL import features
        if not features.check("raqm"):
            print("build_captions: ERROR Urdu captions need libraqm for correct "
                  "script shaping, and this Pillow reports no raqm support. Install "
                  "libraqm (e.g. apt install libraqm0) and a Pillow build that links "
                  "it, then retry.", file=sys.stderr)
            sys.exit(2)
        style = "nastaliq-bar"
        candidates = [args.font_ur, str(SKILL / "assets" / "fonts" / "NotoNastaliqUrdu.ttf"),
                      "fonts/NotoNastaliqUrdu.ttf"]
        font_path = next((c for c in candidates if c and Path(c).is_file()), None)
        if not font_path:
            print("build_captions: ERROR Noto Nastaliq Urdu font not found; pass --font-ur "
                  "(free from Google Fonts). The skill ZIP bundles it under assets/fonts/.",
                  file=sys.stderr)
            sys.exit(2)
        font_size = round(52 * (W / 1920) * (1.5 if H > W else 1.0))
        line_h = round(font_size * 1.9)
        pad_y = round(font_size * 0.55)
    else:
        style = "skill-bar"
        # Font search (v1.7, audit L-02): the v1.4 default was a Linux-only
        # absolute path. Search explicit flag, env override, then the
        # usual per-OS locations for a bold Latin font.
        font_candidates = [args.font_en, os.environ.get("MUSE_MOTION_FONT_EN"),
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                           "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                           "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                           "/Library/Fonts/Arial Bold.ttf",
                           "C:/Windows/Fonts/arialbd.ttf"]
        font_path = next((c for c in font_candidates if c and Path(c).is_file()), None)
        if not font_path:
            print("build_captions: ERROR no bold Latin font found in the standard "
                  "locations; pass --font-en with a TTF path", file=sys.stderr)
            sys.exit(2)
        font_size = round(52 * (W / 1920) * (1.5 if H > W else 1.0))
        line_h = round(font_size * 1.25)
        pad_y = round(font_size * 0.42)
    font = ImageFont.truetype(font_path, font_size)
    pad_x = round(font_size * 1.05)
    # Portrait placement (v1.7, audit H-05): the old 300px default at
    # 1080x1920 parked the bar INSIDE the platform UI band the skill's
    # own reference documents (TikTok bottom band ~350-440px). Default
    # now clears it (460 at 1920 tall, scaled); a Reels deliverable,
    # whose ads guide excludes the bottom ~35%, should pass
    # --bottom-margin explicitly (about 700 at 1080x1920).
    bottom_margin = args.bottom_margin if args.bottom_margin is not None else (
        round(460 * H / 1920) if H > W else 64)
    # Panel can never exceed the canvas (v1.7, H-05): the text budget
    # leaves room for the panel padding plus a 24px edge margin a side.
    max_line_w = W - 2 * pad_x - 48

    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    def text_w(s):
        bb = probe.textbbox((0, 0), s, font=font, direction="rtl" if rtl else "ltr",
                            language="ur" if rtl else "en")
        return bb[2] - bb[0]

    line_char_cap = args.max_chars or DEFAULT_MAX_CHARS[args.lang]

    def wrap_idx(cue_words):
        """Greedy wrap by measured width AND the per-line character cap
        (a cue repaired for phrase integrity may hold two lines of text;
        each rendered line must still respect the cap). Returns lines as
        lists of word indices."""
        lines, cur = [], []
        for wi, w in enumerate(cue_words):
            cand = " ".join(cue_words[j]["text"] for j in cur + [wi])
            if cur and (text_w(cand) > max_line_w or len(cand) > line_char_cap):
                lines.append(cur)
                cur = [wi]
            else:
                cur.append(wi)
        if cur:
            lines.append(cur)
        if len(lines) > 2:
            lines = [lines[0], [j for ln in lines[1:] for j in ln]]
        if len(lines) == 2:
            # balance the pair: a full first line over a stub second line
            # ("...for the night" / "side") reads as a split phrase even
            # inside one cue. Move words down while both lines stay within
            # caps and the length imbalance shrinks.
            def llen(idxs):
                return len(" ".join(cue_words[j]["text"] for j in idxs))
            while len(lines[0]) > 1:
                cand0 = lines[0][:-1]
                cand1 = [lines[0][-1]] + lines[1]
                t0 = " ".join(cue_words[j]["text"] for j in cand0)
                t1 = " ".join(cue_words[j]["text"] for j in cand1)
                if len(t0) > line_char_cap or len(t1) > line_char_cap:
                    break
                if text_w(t0) > max_line_w or text_w(t1) > max_line_w:
                    break
                if abs(len(t0) - len(t1)) >= abs(llen(lines[0]) - llen(lines[1])):
                    break
                lines = [cand0, cand1]
        return lines

    space_w = text_w(" ")

    def render_cue(cue, line_idxs, active_wi):
        lines_text = [" ".join(cue["words"][j]["text"] for j in idxs) for idxs in line_idxs]
        pw = max(text_w(ln) for ln in lines_text) + 2 * pad_x
        if rtl:
            # Measured layout (v1.7, audit M-04): Nastaliq ink is far
            # taller than the nominal line height (87px measured ink vs
            # the 66px the old 1.9x factor allowed at 35px type), so
            # lines overlapped and descenders crowded the underline.
            # Stack lines by their MEASURED ink heights plus a real gap.
            ink_h = []
            for ln in lines_text:
                bb = probe.textbbox((0, 0), ln, font=font, direction="rtl", language="ur")
                ink_h.append(bb[3] - bb[1])
            line_gap = round(font_size * 0.30)
            advances = [h + line_gap for h in ink_h]
            ph = 2 * pad_y + sum(ink_h) + line_gap * (len(ink_h) - 1) + 16
        else:
            advances = [line_h] * len(lines_text)
            ph = line_h * len(lines_text) + 2 * pad_y + 10
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        x0 = (W - pw) // 2
        y0 = H - bottom_margin - ph
        dr.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=20, fill=PANEL)
        dr.rectangle([x0 + 28, y0 + ph - 14, x0 + pw - 28, y0 + ph - 8], fill=AMBER)
        ty = y0 + pad_y
        for li, (idxs, ln) in enumerate(zip(line_idxs, lines_text)):
            lw = text_w(ln)
            # one shared baseline per line (from the full line's bbox) so
            # words without ascenders do not ride high when drawn singly
            line_bb = dr.textbbox((0, 0), ln, font=font, direction="rtl" if rtl else "ltr",
                                  language="ur" if rtl else "en")
            word_y = ty - line_bb[1]
            if rtl:
                cursor = x0 + (pw + lw) // 2  # right edge of the line
                for j in idxs:
                    wtxt = cue["words"][j]["text"]
                    bb = dr.textbbox((0, 0), wtxt, font=font, direction="rtl", language="ur")
                    col = AMBER if j == active_wi else WHITE
                    dr.text((cursor - bb[2], word_y), wtxt, font=font, fill=col,
                            direction="rtl", language="ur")
                    cursor -= text_w(wtxt) + space_w
            else:
                cursor = x0 + (pw - lw) // 2
                for j in idxs:
                    wtxt = cue["words"][j]["text"]
                    bb = dr.textbbox((0, 0), wtxt, font=font)
                    col = AMBER if j == active_wi else WHITE
                    dr.text((cursor - bb[0], word_y), wtxt, font=font, fill=col)
                    cursor += text_w(wtxt) + space_w
            ty += advances[li]
        return img, lines_text

    max_chars = args.max_chars or DEFAULT_MAX_CHARS[args.lang]
    cues, bursts, timing_notes = build_cues(words, max_chars, args.max_cps,
                                            total_duration=args.duration)
    burst_starts = {round(b["start"], 3) for b in bursts}

    out_dir = Path(args.out_dir) if args.out_dir else tpath.with_name(f"captions-{args.lang}")
    png_dir = out_dir / "pngs"
    png_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(png_dir / "gap.png")

    cue_records, srt_blocks, concat = [], [], ["ffconcat version 1.0"]
    prev_end = 0.0
    total_dur = args.duration or (cues[-1]["end"] + 1.0)
    highlight = not args.no_highlight
    for i, cue in enumerate(cues, start=1):
        line_idxs = wrap_idx(cue["words"])
        ws = cue["words"]
        if highlight and len(ws) > 1:
            span = max(ws[-1]["end"] - ws[0]["start"], 0.01)
            scale = (cue["end"] - cue["start"]) / span
            bounds = [cue["start"] + (w["start"] - ws[0]["start"]) * scale for w in ws]
            bounds.append(cue["end"])
            for j in range(len(bounds) - 1):
                if bounds[j + 1] <= bounds[j]:
                    bounds[j + 1] = bounds[j] + 0.05
            states = [(j, bounds[j], min(bounds[j + 1], cue["end"])) for j in range(len(ws))]
        else:
            states = [(None, cue["start"], cue["end"])]
        state_records = []
        lines_text = None
        for (active_wi, frm, to) in states:
            img, lines_text = render_cue(cue, line_idxs, active_wi)
            name = f"cue-{i:04d}.png" if active_wi is None else f"cue-{i:04d}-w{active_wi}.png"
            img.save(png_dir / name)
            state_records.append({"png": f"pngs/{name}", "from": round(frm, 3), "to": round(to, 3)})
        cue_records.append({"start": cue["start"], "end": cue["end"], "lines": lines_text,
                            "png": state_records[0]["png"], "states": state_records})
        srt_blocks.append(f"{i}\n{srt_time(cue['start'])} --> {srt_time(cue['end'])}\n" + "\n".join(lines_text))
        if cue["start"] > prev_end:
            concat += ["file 'pngs/gap.png'", f"duration {cue['start'] - prev_end:.3f}"]
        for sr in state_records:
            concat += [f"file '{sr['png']}'", f"duration {max(sr['to'] - sr['from'], 0.04):.3f}"]
        prev_end = cue["end"]
    if total_dur > prev_end:
        concat += ["file 'pngs/gap.png'", f"duration {total_dur - prev_end:.3f}"]
    concat += ["file 'pngs/gap.png'"]  # concat demuxer needs the last file repeated

    (out_dir / "captions.srt").write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")
    (out_dir / "layer.ffconcat").write_text("\n".join(concat) + "\n")
    meta = {"language": args.lang, "style": style, "canvas": {"width": W, "height": H},
            "source_transcript": str(tpath), "max_chars": max_chars, "max_cps": args.max_cps,
            "dictionary_coverage_percent": coverage, "over_speed_bursts": len(bursts),
            "cues_clamped_to_duration": timing_notes["clamped"],
            "words_dropped_past_duration": timing_notes["dropped"],
            "word_highlight": highlight,
            "cues": cue_records}
    (out_dir / "captions.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))

    # self-check against the caption rules (same limits as check_captions.py);
    # cues inside a declared over-speed burst are warnings, not failures -
    # the speech there is measurably faster than the reading-speed limit.
    problems, burst_notes = [], []
    for i, c in enumerate(cue_records, start=1):
        for ln in c["lines"]:
            if len(ln) > max_chars:
                problems.append(f"cue {i}: line {len(ln)} chars > {max_chars}")
        dur = c["end"] - c["start"]
        chars = len(" ".join(c["lines"]))
        if dur > 0 and chars / dur > args.max_cps:
            if round(c["start"], 3) in burst_starts:
                burst_notes.append(f"cue {i}: {chars / dur:.1f} cps (speech-density burst)")
            else:
                problems.append(f"cue {i}: {chars / dur:.1f} cps > {args.max_cps}")
    print(f"build_captions: {len(cue_records)} cues ({args.lang}/{style}) -> {out_dir}")
    for bn in burst_notes:
        print(f"build_captions: WARN {bn}")
    if timing_notes["clamped"]:
        print(f"build_captions: WARN {timing_notes['clamped']} cue(s) clamped to the "
              f"timeline duration ({args.duration}s) - they could not hold their "
              "full reading time (audit H-04 declaration)")
    if timing_notes["dropped"]:
        print(f"build_captions: WARN {timing_notes['dropped']} cue(s) dropped - their "
              "words start past the timeline duration")
    if coverage is not None:
        print(f"build_captions: roman dictionary coverage {coverage}% "
              f"({'good' if coverage >= 85 else 'REVIEW spellings - coverage is low'})")
    if problems:
        for p in problems:
            print(f"build_captions: SELF-CHECK FAIL {p}")
        sys.exit(1)
    print("build_captions: self-check PASS (line length + reading speed)")


if __name__ == "__main__":
    main()
