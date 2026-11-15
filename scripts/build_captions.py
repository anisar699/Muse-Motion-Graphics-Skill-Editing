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
    words = []
    for seg in transcript.get("segments", []):
        sw = seg.get("words") or []
        if sw:
            for w in sw:
                t = (w.get("word") or "").strip()
                if t:
                    words.append({"text": t, "start": float(w["start"]), "end": float(w["end"])})
        elif seg.get("text"):
            parts = seg["text"].split()
            if parts:
                step = (float(seg["end"]) - float(seg["start"])) / len(parts)
                for i, t in enumerate(parts):
                    words.append({"text": t, "start": float(seg["start"]) + i * step,
                                  "end": float(seg["start"]) + (i + 1) * step})
    return words


def build_cues(words, max_chars, max_cps, max_dur=6.5, gap_break=0.6):
    """Caption timing model (the way captioners actually solve it):
    words are grouped into BLOCKS separated by real pauses (> gap_break).
    Inside a block the timeline is tiled proportionally to each cue's
    character count, so every cue sits at the block's average reading
    speed instead of inheriting Whisper's compressed word end-times.
    A block borrows its trailing pause (up to the next block) and up to
    0.3s of anticipation. If a block's own average still exceeds max_cps
    the speech there is genuinely faster than the limit; those cues are
    returned in `bursts` and reported, never hidden."""
    # 1) blocks
    blocks, cur = [], [words[0]]
    for w in words[1:]:
        if w["start"] - cur[-1]["end"] > gap_break:
            blocks.append(cur)
            cur = []
        cur.append(w)
    blocks.append(cur)

    norm, bursts = [], []
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
        # 3) block window
        b_start = block[0]["start"]
        if bi > 0:
            b_start = max(b_start - 0.3, norm[-1]["end"] + 0.08) if norm else b_start
        b_end = block[-1]["end"]
        if bi + 1 < len(blocks):
            b_end = min(b_end + 1.5, blocks[bi + 1][0]["start"] - 0.08)
        total_chars = sum(sum(len(x["text"]) for x in g) + len(g) - 1 for g in groups)
        window = max(b_end - b_start, total_chars / max_cps)  # never compress below the limit's need
        if bi + 1 < len(blocks):
            window = min(window, blocks[bi + 1][0]["start"] - 0.08 - b_start)
        avg_cps = total_chars / max(window, 0.01)
        # 4) tile proportionally, then water-fill: no cue may end up shorter
        # than 0.7s (time is taken from the block's longer cues, never from
        # neighbouring blocks), and bursts are judged on FINAL durations.
        char_list = [sum(len(x["text"]) for x in g) + len(g) - 1 for g in groups]
        durs = [window * (c / total_chars) if total_chars else window / len(groups)
                for c in char_list]
        for _ in range(len(groups)):
            deficit = sum(max(0.0, 0.7 - d) for d in durs)
            surplus = sum(d - 0.7 for d in durs if d > 0.7)
            if deficit <= 0 or surplus <= 0:
                break
            take = min(deficit, surplus)
            durs = [d + take * (0.7 - d) / deficit if d < 0.7
                    else d - take * (d - 0.7) / surplus if d > 0.7 else d
                    for d in durs]
        t = b_start
        for gi, g in enumerate(groups):
            start = t
            end = t + durs[gi]
            cue = {"start": round(start, 3), "end": round(end, 3), "words": g}
            if char_list[gi] / max(durs[gi], 0.01) > max_cps:
                bursts.append(cue)
            norm.append(cue)
            t = end + 0.001
    return norm, bursts


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
    ap.add_argument("--font-en", default="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
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
    transcript = json.loads(tpath.read_text())
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

    words = load_words(transcript)
    if not words:
        print("build_captions: ERROR transcript has no words/segments", file=sys.stderr)
        sys.exit(2)

    coverage = None
    if args.lang == "roman":
        dictionary = json.loads(Path(args.dictionary).read_text(encoding="utf-8"))["words"]
        hits = 0
        for w in words:
            w["text"], hit = transliterate(w["text"], dictionary)
            hits += hit
        coverage = round(100.0 * hits / len(words), 1)

    try:
        W, H = (int(x) for x in args.video.lower().split("x"))
    except Exception:
        print("build_captions: ERROR --video must look like 1920x1080", file=sys.stderr)
        sys.exit(2)

    from PIL import Image, ImageDraw, ImageFont
    rtl = args.lang == "ur"
    if rtl:
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
        font_path = args.font_en
        if not Path(font_path).is_file():
            print(f"build_captions: ERROR font not found: {font_path} (pass --font-en)", file=sys.stderr)
            sys.exit(2)
        font_size = round(52 * (W / 1920) * (1.5 if H > W else 1.0))
        line_h = round(font_size * 1.25)
        pad_y = round(font_size * 0.42)
    font = ImageFont.truetype(font_path, font_size)
    pad_x = round(font_size * 1.05)
    bottom_margin = args.bottom_margin if args.bottom_margin is not None else (300 if H > W else 64)
    max_line_w = W - 2 * (90 if W >= 1280 else 40)

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
        ph = line_h * len(lines_text) + 2 * pad_y + 10
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        x0 = (W - pw) // 2
        y0 = H - bottom_margin - ph
        dr.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=20, fill=PANEL)
        dr.rectangle([x0 + 28, y0 + ph - 14, x0 + pw - 28, y0 + ph - 8], fill=AMBER)
        ty = y0 + pad_y
        for idxs, ln in zip(line_idxs, lines_text):
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
            ty += line_h
        return img, lines_text

    max_chars = args.max_chars or DEFAULT_MAX_CHARS[args.lang]
    cues, bursts = build_cues(words, max_chars, args.max_cps)
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
