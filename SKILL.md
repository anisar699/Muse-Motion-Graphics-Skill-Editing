---
name: muse-motion
description: Professional motion graphics video editing for user-supplied videos. Use for kinetic typography, titles, lower thirds, animated captions, callouts, logo animation, transitions, data visualisation, UI mockups, social formats, explainer and whiteboard elements, 2.5D parallax, 3D basics, character basics, product promos, lyric videos, intros, outros and CTAs, with a directive-first Remotion, ffmpeg and Python workflow.
---

# Muse Motion

Version 1.6 (2026-11-15). Changes from 1.0 are listed in CHANGELOG.md.

## Purpose and route selection

- Use this skill for every video editing task that needs motion graphics, animated text, graphics overlays, transitions, captions, data animation, or a full motion led edit in any format.

- Work as Muse itself with the local code stack of Remotion, ffmpeg, and Python. Do not require Codex, OpenAI, or an After Effects GUI unless the user explicitly orders a different route.

- Route the job by duration and format before building (routes defined in references/workflow-and-directive.md). Fast intro: a title or bumper of at most 15s, usually graphics-only. Short form: at most 90s vertical or square social video. Long form: over 90s, footage-led. Graphics only: no camera footage - lyric videos, logo animation, stills-and-type explainers; the directive source is kind "audio" or kind "none" with timeline.duration_s.

- Never modify the original media. Copy source files into the project folder, keep originals untouched, and write every output under the project edit folder.

- Read the installed Remotion version docs at build time when an API detail matters. Remotion v4 changes often, so do not trust a remembered API over the installed package docs.

## Fast professional workflow

- Start with intake. Probe every source with ffprobe, record width, height, exact frame rate, duration, codec, colour, and audio sample rate, and list the deliverables, platforms, aspects, caption needs, and deadline in the brief template. If the colour tags are not BT.709 SDR, resolve the source through the non-BT.709 route in references/ffmpeg-and-audio.md (convert BT.2020 SDR pixels, or stop and report PQ/HLG as unsupported) before designing anything; never relabel tags without converting pixels.

- Transcribe locally before designing anything. Extract 16 kHz mono audio with ffmpeg, run faster-whisper with word timestamps, cache the transcript JSON, and flag every word with probability below 0.80 for a human check of names and numbers.

- Group words into complete semantic beats. Mark each beat role with exactly one of the validator role tokens, all lowercase: hook, context, problem, promise, reveal, definition, process, proof, reassurance, transition, cta.

- Write the director treatment and the editorial directive JSON before any graphics. Validation is two-stage: run scripts/validate_directive.py with --draft while designing (schema gate only, a draft PASS is never render permission), and run it without --draft before rendering (render-ready gate: approval.status must be approved with zero ambiguities, the source media must exist and probe with a matching duration, layouts must sit inside the canvas, protected regions are collision-checked (fail at 10 percent of the region, 50 percent of the layout, or any overlap of a critical region; overrides need the boolean true plus an overlap_reason and are always reported), roles, treatments and transition tokens must come from the fixed sets in references/workflow-and-directive.md, and reveal_sync elements must be declared in on_screen_copy). Any INVALID result stops the render.

- Build styleframes before animation. Render one finished still each for the title, a typical scene, a data scene, the lower third, and the end card, and lock fonts, colours, spacing, safe areas, and motion tokens from those frames.

- Build an animatic when timing is not already locked. Render the real composition with styleframe stills, final timing, and scratch or final audio at half scale, and check pacing on that file before full animation.

- Animate in passes. Block the key poses first, add easing and springs second, add stagger and follow through third, and sync sound hits last within one frame of the visual landing.

- Composite graphics before captions. Add captions last so they stay on top and inside the delivery safe area.

- Verify the finished file before delivery. Follow the verification gate in this skill and never deliver on a render success message alone.

## Editorial rules

- Give each timeline interval exactly one primary treatment, using the validator treatment tokens exactly: CLEAN_PRESENTER, OVERLAY_CARD, FULLSCREEN_MOTION, PRESENTER_INSET, SELECTIVE_TEXT, TRANSITION, KINETIC_TYPE, DATA_SCENE, CALLOUT, LOWER_THIRD, TITLE, END_CARD.

- Protect the presenter. Keep faces, eyes, microphones, and the main gesture corridor clear, and check protection on the actual footage rather than on a blank canvas.

- Let meaning lead motion. Animate only words and elements that carry meaning such as nouns, verbs, numbers, and contrasts, and keep filler words stable.

- Keep one primary animating element per beat. Secondary action may support the main action but must never compete with it.

- Hold every resolved graphic long enough to read. A hold shorter than its entrance plus exit is a defect.

- Use official brand logos only. Fetch each named brand logo from its own press kit or brand page, record the source, and never draw, trace, recolour, or replace a logo with typed text or a generic icon.

- Keep on screen copy faithful to the spoken claim. Condense when needed, and never silently rewrite or invent a claim.

- Put no logo sting, greeting, or slow opener before the hook in online video. Stack the hook as a visual interrupt, a spoken promise, and on screen text in the first seconds.

## Motion defaults

- Match the source frame rate for edits. Use 30 fps for new web and social motion comps, 24 fps only for cinematic work, and 60 fps only for gaming, sport, or fast screen capture.

- Never use linear easing for position or scale. Use ease out for entrances, ease in for exits, and ease in out for moves that stay on screen, and reserve linear only for loops, progress bars, and time driven values.

- Use the house curves from the motion reference. The workhorse entrance curve is cubic bezier 0.16, 1, 0.3, 1, the Material standard curve is 0.2, 0, 0, 1, and the overshoot curve is 0.34, 1.56, 0.64, 1 used sparingly.

- Use springs for organic entrances and follow through. Use damping 200 for a smooth no bounce settle, damping 12 to 15 for a playful bounce, and damping 20 with stiffness 200 and mass 0.8 for a snappy pop.

- Keep standard entrances between 250 and 500 ms. Keep exits at about 60 to 75 percent of the entrance duration, keep micro moves between 100 and 200 ms, and keep almost no interface like move above 500 ms.

- Add anticipation as a small counter move of about 5 to 10 percent of the travel over 3 to 6 frames at 30 fps. Add follow through by staggering secondary elements 2 to 4 frames after the main element lands.

- Use a 180 degree shutter feel as the motion blur default when graphics must match live footage. Disable blur emulation on text that must be read and on data values.

## Element playbooks

- Follow the taxonomy playbook reference for the exact spec of each element. It covers kinetic typography, titles, lower thirds, captions, callouts, logo animation, transitions, data visualisation, UI mockups, social elements, explainer and whiteboard, parallax, 3D, character basics, product promo, lyric video, and end cards.

- Build lower thirds with the accent first, the name second, and the role third. Use about 15 frames for the entrance at 30 fps, hold at least 3 seconds, and keep the total between 3 and 5 seconds.

- Treat accessibility captions and animated social captions as different products. Accessibility captions stay faithful with no decorative animation, while social captions use word level highlighting inside the same Sequence as the clip they caption.

- Animate data honestly. Grow bars from the baseline, draw lines in time order, count numbers up with ease out to the exact final value, and never overshoot a data value.

- Keep transitions as punctuation. Prefer a hard cut by default, use dissolves for time passing, and use wipes, whip pans, zooms, morphs, and match cuts only when the relationship between scenes calls for them.

- Build parallax from separated depth planes. Move foreground fastest, midground slower, and background slowest, and keep virtual camera angles modest so flat layers never reveal themselves.

## Code production rules

- Derive every animation from the current frame. Use useCurrentFrame and useVideoConfig for all motion, and never use CSS transitions, CSS animations, timers, or unseeded random values.

- Clamp every bounded interpolate call on both sides. Write timing in seconds multiplied by fps in code, and keep frame numbers with a seconds comment when a bare number is unavoidable.

- Prefer inline interpolate with individual scale, translate, and rotate properties over composed transform strings. Use interpolate for beat exact timing and loops, and use springs when organic settle matters more than an exact frame.

- Structure every deliverable as a registered Composition with data driven duration through calculateMetadata where timing comes from captions or a beat grid. Build scenes as Sequence or Series blocks and transitions with TransitionSeries.

- Load fonts explicitly at module top level with narrowed weights. Load media with the Remotion media components that block rendering until assets are ready, and use delayRender only with a clear continue path.

- Preserve alpha through every link when an overlay is the deliverable. Render PNG frames and finish as ProRes 4444 with yuva444p10le for editors, VP9 WebM with yuva420p for browsers, or a PNG sequence as the most portable form, and never promise alpha in H.264 MP4.

- Remember the proven alpha lesson from real production. Direct Remotion video renders can silently drop alpha, so the safe route is a PNG sequence rendered first and then encoded with ffmpeg prores_ks 4444, followed by a pixel format check that confirms an alpha plane exists.

- Speed renders deliberately. Use JPEG frames for opaque comps and PNG only for alpha, draft at half scale for timing approvals, re render only the fixed frame range after a local fix, and benchmark concurrency on the actual machine.

## Audio, loudness, and export

- Mix voice first, duck music under voice, and place sound effects on visual landings sparingly with one effect family per brand. Normalise the final mix as a whole and never normalise clip by clip.

- Use minus 14 LUFS integrated and at most minus 1 dBTP as the working target for YouTube and social delivery. Use minus 16 LUFS for spoken podcasts, minus 23 LUFS for EBU R 128 broadcast, and minus 24 LKFS for ATSC broadcast.

- State the loudness caveat when reporting. YouTube publishes no LUFS target, so minus 14 is an inferred working default from player normalisation data, not a published platform rule.

- Normalise with two pass loudnorm for deliverables. Measure first, then apply with the measured values and linear true, because single pass loudnorm processes dynamically and can pump the mix.

- Export long form as MP4 with H.264 High Profile, progressive, 4.2.0, VBR, and AAC LC at 48 kHz. Use 8 Mbps for 1080p at 30 fps, 12 Mbps at 60 fps, 16 and 24 Mbps for 1440p, and 35 to 45 Mbps for 4K at 30 fps.

- Export one vertical master at 1080 by 1920, 9 to 16, 30 fps, and 10 to 16 Mbps for Shorts, Reels, and TikTok. Render per platform variants from the same composition when safe zones differ.

## Captions (v1.4 caption engine)

- House styles are locked (owner decision 2026-11-15): English and Roman Urdu use the `skill-bar` (charcoal bar, white bold text, amber underline); Urdu script uses the `nastaliq-bar` (same bar, bundled Noto Nastaliq Urdu, RTL). Both bars include word-by-word highlighting: the word being spoken turns amber inside the bar (one PNG state per word). A directive declares captions in its `captions` block (mode none|sidecar|burned|both, language en|ur|roman, style, highlight word|none, source = the captions.json to burn); deviating from the house style warns, and burned mode at the approval gate requires an existing captions source.

- Build captions with scripts/build_captions.py from a word-timestamped transcript (scripts/transcribe.py output). It writes captions.json, captions.srt, and an ffmpeg concat overlay layer (layer.ffconcat) that is overlaid on the source exactly like a graphics layer, so captions can never collide with protected regions by accident and stay in sync with the directive's canvas. Cue timing is reading-time based (block-proportional tiling at <=20 cps); cues that genuinely cannot fit because the speech itself is faster are declared as over-speed bursts in captions.json, never silently hidden.

- Cue grouping repairs broken phrases before tiling (v1.6, owner audit 2026-11-15): a short trailing word that completes a phrase is swallowed into its cue instead of split off ("night side"), one-word tail cues are merged into the previous cue instead of flashing ("routine."), a cue never ends on a function word when the phrase continues ("A city in / space."), and two-line cues are length-balanced. A new sentence's first word is never swallowed across a sentence end. Rendered lines respect the per-line character cap as well as the measured width.

- Heading and fact cards sit in the top zone when captions are burned (caption-zone placement rule - see references/workflow-and-directive.md); the validator warns PLACEMENT when a card layout enters the bottom 26 percent of the frame.

- Language honesty is enforced by the tool: an English transcript yields English captions; an Urdu transcript yields Urdu script and Roman Urdu (transliterated via references/roman-urdu-dictionary.json, with the dictionary coverage percentage reported - extend the dictionary when coverage drops). English-to-Urdu or English-to-Roman is translation, not transcription: the tool refuses it unless a human supplies or approves the translated text.

## Verification gate

- Inspect frames at the hook, every scene hero moment, every entrance and exit, every transition, and the final frame. Compare hero frames against the approved styleframes.

- Check safe areas with an overlay. Keep 16 to 9 text inside the 90 percent title safe area, and keep vertical critical content out of the top platform band, the bottom caption band, and the right action rail.

- Check captions by ear and eye. Confirm names, numbers, and low confidence words, keep standard captions at or below 42 characters per line and 2 lines, and keep reading speed at or below 20 characters per second for adults. Run scripts/check_captions.py on the SRT to automate the form checks (line length, reading speed, cue duration, overlaps, and WCAG contrast when style colours are given); wording stays a human judgement. For speech sources, scripts/transcribe.py produces the word-timestamped transcript locally (faster-whisper, PCM route) that captions and beats are timed from.

- Measure loudness and true peak on the final encoded file, not on the project. First run scripts/peak_guard.py on the encoded file: the AAC encode can overshoot loudnorm's true-peak ceiling (measured -0.95 and -0.7 dBTP against a -1.0 ceiling on real deliveries), and the guard applies the smallest sufficient gain reduction as an audio-only remux and re-measures. Then run scripts/qc_probe.py on the final file with a per-deliverable --spec file and save the --report JSON: it enforces audio presence (missing audio fails as AUDIO_STREAM_MISSING, digital silence fails as AUDIO_SILENT), loudness target and tolerance, true peak ceiling, dimensions, frame rate (0.01 tolerance, VFR detected), codec, pixel format, profile, colour tags, duration, alpha when required (format AND decoded content - a constant-opaque alpha fails), and front placed moov atom when the spec requires faststart (a per-deliverable policy since v1.5: web MP4 specs require it, editor-master and alpha specs do not), and it exits nonzero on any failure; spec keys are whitelisted, and starter specs live in templates/. Use scripts/sample_frames.py to extract hook, quarter, hero, three-quarter and end frames plus a contact sheet for the human visual check (with --directive it also samples every beat start, reveal and end).

- Apply the accessibility hard limits. Keep contrast at or above 4.5 to 1 for normal text and 3 to 1 for large text, and never flash more than 3 times in any 1 second period.

- Report exactly what was verified and what was not. Separate render success, frame inspection, loudness measurement, and device or platform preview into distinct claims.

- Never claim what was not verified. This skill package does not bundle a complete Remotion sample project, so do not claim the archive itself was render-proven; claim only the renders actually produced in the current workspace. Automated gates never replace human sign-off for narrative truth, visual taste, caption accuracy, or face protection on moving footage.

## References in this skill

- Read references/motion-principles-and-easing.md for the 12 principles, the full easing library, duration tables, frame rates, and motion blur.

- Read references/taxonomy-playbook.md for the per element specs for all 17 motion graphics element families.

- Read references/workflow-and-directive.md for intake, transcription, storyboard, styleframes, animatic, and the directive rules.

- Read references/remotion-code-patterns.md for composition structure, animation patterns, alpha workflow, and render performance.

- Read references/ffmpeg-and-audio.md for compositing commands, two pass loudnorm, and caption audio preparation.

- Read references/export-presets-and-qc.md for export tables and the full quality control checklist.

- Read references/platform-retention-accessibility.md for hook and pacing heuristics, vertical safe zones, and accessibility limits, with every practitioner heuristic labelled as a heuristic.

- Read references/research-sources.md for the source list and the open questions that must not be presented as settled standards.

- Use templates/brief-template.md at intake, templates/editorial-directive-template.json for the directive, and templates/qc-checklist.md before delivery.

- Run scripts/validate_directive.py on every directive JSON before rendering, and run scripts/qc_probe.py on every final file before delivery. Speech work: scripts/transcribe.py (local word timestamps), scripts/build_captions.py (caption engine), scripts/check_captions.py (SRT form checks), scripts/peak_guard.py (encoded-file true-peak fix).

## Available connectors

- [Google Drive](/opt/hatch/connectors/google_drive/CONNECTOR.md) for delivering finished videos and skill packages when the user asks for a Drive link.

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.
