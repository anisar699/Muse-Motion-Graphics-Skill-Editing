#!/usr/bin/env python3
"""Muse Motion local transcription (v1.3).

Step 0 of the workflow, now built into the skill: transcribe the source
locally with faster-whisper and write the transcript JSON the directive
design works from. Nothing is uploaded anywhere.

The audio is decoded to 16 kHz mono PCM with ffmpeg and fed to Whisper as a
numpy array. Feeding the media file directly hits a PyAV build bug
(av.open() rejects the metadata_errors keyword) on some installations; the
PCM route works everywhere.

Usage:
  python3 transcribe.py MEDIA [--out transcript.json] [--model small]
                      [--language en] [--device cpu] [--compute int8]

Output JSON: {"language": ..., "segments": [{"start", "end", "text",
"words": [{"word", "start", "end", "probability"}]}],
"low_probability_words": [...]} - words below 0.80 probability are listed
for the human check of names and numbers the workflow requires.
Default output is "<media-stem>.transcript.json" in the CURRENT directory
(v1.7, audit M-07: v1.3 wrote into the source folder, polluting - or
failing on - media libraries the user never asked to write into).
Exit codes: 0 ok, 2 tool error (missing file/ffmpeg/faster-whisper).
"""
import argparse
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--out")
    ap.add_argument("--model", default="small")
    ap.add_argument("--language")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--compute", default="int8")
    args = ap.parse_args()

    src = Path(args.media)
    if not src.is_file():
        print(f"transcribe: ERROR file not found: {src}", file=sys.stderr)
        sys.exit(2)
    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError as e:
        print(f"transcribe: ERROR missing dependency ({e}); "
              "install the skill's requirements.txt", file=sys.stderr)
        sys.exit(2)

    out_path = Path(args.out) if args.out else Path.cwd() / f"{src.stem}.transcript.json"

    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "audio16k.wav"
        try:
            r = subprocess.run(
                ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(src),
                 "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
                capture_output=True, text=True)
        except FileNotFoundError:
            print("transcribe: ERROR ffmpeg is not available on PATH", file=sys.stderr)
            sys.exit(2)
        if r.returncode != 0:
            print(f"transcribe: ERROR ffmpeg decode failed: {r.stderr[-500:]}",
                  file=sys.stderr)
            sys.exit(2)
        with wave.open(str(wav), "rb") as w:
            pcm = (np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                   .astype(np.float32) / 32768.0)

    try:
        model = WhisperModel(args.model, device=args.device, compute_type=args.compute)
        segments, info = model.transcribe(pcm, language=args.language,
                                          word_timestamps=True)
        out = {"language": info.language, "segments": []}
        low_prob = []
        for s in segments:
            seg_words = [{"word": w.word, "start": round(w.start, 3),
                          "end": round(w.end, 3),
                          "probability": round(w.probability, 3)}
                         for w in (s.words or [])]
            for w in seg_words:
                if w["probability"] < 0.80:
                    low_prob.append(w)
            out["segments"].append({
                "start": round(s.start, 3), "end": round(s.end, 3),
                "text": s.text.strip(), "words": seg_words})
    except Exception as e:
        print(f"transcribe: ERROR transcription failed: {e}", file=sys.stderr)
        sys.exit(2)
    out["low_probability_words"] = low_prob
    out_path.write_text(json.dumps(out, indent=1))
    print(f"transcribe: {len(out['segments'])} segments, "
          f"language={out['language']} -> {out_path}")
    if low_prob:
        print(f"transcribe: {len(low_prob)} word(s) below 0.80 probability - "
              "human check of names and numbers required (listed in the JSON)")


if __name__ == "__main__":
    main()
