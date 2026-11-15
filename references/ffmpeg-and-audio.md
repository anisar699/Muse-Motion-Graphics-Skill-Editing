# ffmpeg Compositing, Loudness and Caption Audio

## Compositing overlays

PNG sequence overlay over user footage in a timed window:
ffmpeg -i footage.mp4 -framerate 30 -i frames/frame_%04d.png -filter_complex "[0:v][1:v]overlay=0:0:enable='between(t,2.0,7.5)'[out]" -map "[out]" -map 0:a -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a copy out.mp4

Single transparent video overlay:
ffmpeg -i footage.mp4 -i overlay.mov -filter_complex "[0:v][1:v]overlay=x=0:y=0:shortest=1[out]" -map "[out]" -map 0:a -c:v libx264 -crf 18 -pix_fmt yuv420p out.mp4

Rules are background stream first and overlay second, and forcing format yuva444p preserves cleaner edges than yuva420p which subsamples chroma and alpha and fringes on thin lines. Many ffmpeg filters silently drop alpha unless format is forced. End alpha deliverables in ProRes 4444, VP9 WebM or PNG sequence, never MP4 H.264. Other toolbox filters are xfade and acrossfade for transitions, drawtext, subtitles and ass for quick burned captions with ASS for karaoke styling, loudnorm and ebur128 for loudness, thumbnail and select for QC frame grabs, and silencedetect for pause cutting.

## Loudness targets

All measurement follows ITU-R BS.1770 with K weighting and gating, and LUFS equals LKFS numerically.
- YouTube, social and Spotify working target is minus 14 LUFS integrated and at most minus 1 dBTP. YouTube publishes no loudness number, so this is inferred from player Stats for nerds normalisation data and is a working default, not a published rule.
- Apple Podcasts and streaming spoken word is minus 16 LUFS and at most minus 1 to minus 1.5 dBTP.
- EU broadcast EBU R 128 is minus 23.0 LUFS and at most minus 1 dBTP, with tolerance of plus or minus 1.0 LU only where the target is impractical such as live, and plus or minus 0.2 LU in QC for meter error.
- US broadcast ATSC A/85 is minus 24 LKFS and minus 2 dBTP.
- Netflix dialog gated at minus 27 LKFS is not comparable to programme gated numbers because the measurement differs.

## Two pass loudnorm

Always use two pass loudnorm for deliverables. Single pass uses dynamic processing that estimates as it goes and can pump or alter the mix. Two pass with linear true applies one static gain from the full programme measurement, leaving dynamics and timing untouched. Linear falls back to dynamic if measured values are missing or gain would push peaks over the true peak ceiling.

Pass one measures with no file written and JSON printed:
ffmpeg -i mix.wav -af "loudnorm=I=-14:TP=-1:LRA=11:print_format=json" -f null -

Pass two applies with the measured values fed back:
ffmpeg -i mix.wav -af "loudnorm=I=-14:TP=-1:LRA=11:measured_I=<measured>:measured_TP=<measured>:measured_LRA=<measured>:measured_thresh=<measured>:offset=<measured>:linear=true" -ar 48000 final.wav

Parameters are I as integrated LUFS target, TP as true peak ceiling with minus 1.5 or minus 2 giving extra codec headroom for spoken word, and LRA as loudness range target with 7 LU for tight broadcast style and 11 LU for natural spoken and social. Filter defaults of I minus 24, TP minus 2 and LRA 7 must never be relied on for social delivery. Verify after encoding with a measurement pass on the final file.

## Sound design

Mix voice first with clean edits and de essing, duck music under voice with music typically sitting about minus 18 to minus 25 LUFS short term under dialogue as a practitioner range to verify by ear and meter per mix, and place effects hits on visual landings such as whoosh on wipes and pop on springs sparingly with one effect family per brand. Sync tolerance is within plus or minus 1 frame of the visual event. Normalise the final mix as a whole and never per clip.

## Caption audio preparation

Extract audio for speech recognition as 16 kHz mono:
ffmpeg -i input.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le audio.wav

Transcribe with faster-whisper and word_timestamps true. Each segment gives words with word, start, end and probability. Flag probability below 0.80 for human check. Model small is a sensible laptop default, while medium or large turbo is cleaner on messy audio and proper names but slower. Normalise output to the Remotion Caption shape of text, startMs, endMs, timestampMs and confidence per word. Group words into TikTok style pages inside the same Sequence as the clip, highlight the active word from its timestamps, and also emit SRT and VTT sidecars from the same JSON. Cache transcription JSON keyed by audio hash, because transcription is a batch step that should run once.


## Overlay precision, faststart, and voice ducking (v1.1)

Composite PNG sequence overlays with format=auto so ffmpeg keeps high precision alpha internally and thin kinetic type edges do not fringe, and always write web deliverables with +faststart:

ffmpeg -i footage.mp4 -framerate 30 -i frames/frame_%04d.png -filter_complex "[0:v][1:v]overlay=0:0:format=auto:enable='between(t,2.0,7.5)',format=yuv420p[out]" -map "[out]" -map 0:a -c:v libx264 -profile:v high -crf 18 -c:a aac -b:a 384k -ar 48000 -movflags +faststart out.mp4

Duck background music under the voice with a sidechain compressor driven by the voice track, instead of a fixed music volume:

ffmpeg -i voice.wav -i music.wav -filter_complex "[1:a]volume=0.35[bg];[bg][0:a]sidechaincompress=threshold=0.03:ratio=6:attack=50:release=400[ducked];[0:a][ducked]amix=inputs=2:duration=first[mix]" -map "[mix]" -ar 48000 mix.wav
