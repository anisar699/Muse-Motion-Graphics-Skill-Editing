# Research Sources and Open Questions

Research run on 15 Nov 2026 for Muse Motion. The full research report is kept in the workspace research notes for muse-motion-graphics-research-20261115-0802. Values in this skill come from that report. Treat practitioner heuristics as heuristics.

## Official and primary sources

Canonical links (added v1.2):
- EBU R 128 loudness recommendation: tech.ebu.ch/publications/r128
- ITU-R BS.1770 loudness measurement: itu.int/rec/R-REC-BS.1770
- WCAG 2.2 (captions 1.2.2, contrast 1.4.3, flashing 2.3.1): w3.org/TR/WCAG22
- YouTube recommended upload encoding settings: support.google.com/youtube/answer/1722171
- Remotion documentation: remotion.dev/docs

## Official and primary sources (research notes)

- Remotion rendering transparent videos, read live at remotion.dev/docs/transparent-videos
- Remotion flickering and determinism, read live at remotion.dev/docs/flickering
- Remotion interactivity best practices at remotion.dev/docs/studio/interactivity-best-practices
- Remotion captioning in the Editor Starter at remotion.dev/docs/editor-starter/captioning
- Adobe After Effects assorted animation tools on motion blur and shutter, read live at helpx.adobe.com
- EBU R 128 values through a document based summary of R 128 v5.0 Nov 2023 and BS.1770-5
- NUGEN Audio broadcast loudness summary for EBU R 128 and BBC practice

## Standards summaries and platform specs

- YouTube Help upload settings through checked summaries of the YouTube bitrate tables
- Mark Studios LUFS meter reading YouTube minus 14 from player data across 26 videos in Oct 2026
- Northwest Media Systems platform loudness cheat sheet
- Versely loudness targets by destination with the Netflix dialog gated warning
- Netflix and BBC caption limits through timed text guide summaries
- SMPTE ST 2046-1 and EBU R 95 safe areas through a standards summary
- Vertical specs and safe zones through current format guides and the Meta ads guide percentages
- WCAG contrast, captions and flashing through W3C WCAG 2.2 summaries for 1.4.3, 1.2.2 and 2.3.1

## Motion design and workflow references

- The 12 principles from Thomas and Johnston, The Illusion of Life 1981, through Toon Boom and motion design references
- Material Design 3 motion tokens and easing through M3 quoting references
- Easing curve libraries for Remotion Easing.bezier values
- Motion graphics direction and taxonomy references including open Remotion motion graphics skills
- Workflow references on the brief to final render chain and styleframe practice
- 2.5D and parallax references on layer speed differentials
- Motion blur practice on the 180 degree rule

## Code production references

- Remotion best practices and stack references on interpolate, spring, Sequence and rendering
- Alpha pitfalls in production reports on PNG sequence delivery
- ffmpeg loudnorm two pass guides
- ffmpeg alpha compositing references
- Whisper and faster-whisper caption guides on word timestamps

## Retention references are practitioner sources

Retention guides from creator tool blogs were used for hook windows, pattern interrupt cadence and retention benchmarks. Their percentages come from analysed samples with varying methods, not from YouTube, TikTok or Meta publications.

## Open questions that must not be presented as settled

- YouTube, TikTok and Instagram publish no loudness target. Minus 14 LUFS is an inferred working default, not a platform rule.
- Retention percentages and safe zone pixels are third party approximations. Safe zones change with app UI updates.
- No universal standard exists for lower third total duration or logo sting length. The 3 to 5 second and 2 to 4 second ranges are strong conventions, not standards.
- Remotion API details change with frequent v4 patches. Check the installed version docs at build time.
- Concurrency and storage numbers must be benchmarked on the actual machine used for rendering.
