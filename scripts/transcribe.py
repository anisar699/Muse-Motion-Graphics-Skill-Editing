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
"words": [{"word", "start", "end", "probability"}]}]}
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

    out_path = Path(args.out) if args.out else src.with_name("transcript.json")

    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "audio16k.wav"
        r = subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(src),
             "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
            capture_output=True, text=True)
        if r.returncode != 0:
            print(f"transcribe: ERROR ffmpeg decode failed: {r.stderr[-500:]}",
                  file=sys.stderr)
            sys.exit(2)
        with wave.open(str(wav), "rb") as w:
            pcm = (np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                   .astype(np.float32) / 32768.0)

    model = WhisperModel(args.model, device=args.device, compute_type=args.compute)
    segments, info = model.transcribe(pcm, language=args.language,
                                      word_timestamps=True)
    out = {"language": info.language, "segments": []}
    for s in segments:
        out["segments"].append({
            "start": round(s.start, 3), "end": round(s.end, 3),
            "text": s.text.strip(),
            "words": [{"word": w.word, "start": round(w.start, 3),
                       "end": round(w.end, 3),
                       "probability": round(w.probability, 3)}
                      for w in (s.words or [])]})
    out_path.write_text(json.dumps(out, indent=1))
    print(f"transcribe: {len(out['segments'])} segments, "
          f"language={out['language']} -> {out_path}")


if __name__ == "__main__":
    main()
