# Professional Workflow and Directive

Canonical chain is Brief, Concept, Script, Storyboard, Styleframes, Animatic, Asset Preparation, Animation, Compositing, Sound, Review, Render and QC, Delivery. The styleframe is the last cheap moment to change how a piece looks and the animatic is the last cheap moment to change timing. Preserve both gates even when moving fast. A one frame styleframe render and a timed slideshow animatic cost minutes in code and save re renders.

## Intake and brief

Use a written brief naming audience, single message, platforms and aspects, duration, deliverables list, deadline, brand assets and rights, and approval owner. Also capture source files with ffprobe specs, voice route of recorded or TTS or none, music rights, caption languages, and the export matrix before any animation.

## Transcription and timing

The first production artefact for any speech video is a word timestamped transcript. It drives caption pages, kinetic type hits, cut points on phrase boundaries, B roll and callout placement, and the animatic. Cut pauses above about 0.3 seconds in short form as a practitioner retention heuristic. For music, build a beat grid of BPM and downbeats in the same timeline JSON. Everything downstream consumes word objects with text, startMs and endMs plus beat and scene markers. Never hand type timings.

## Script and storyboard

A timed script must fit duration at about 130 to 160 spoken words per minute for comfortable narration. The storyboard has one panel per shot or scene tied to a script line with transition and graphic notes. In code the storyboard is the composition outline, so the scene list becomes the Sequence list with from and durationInFrames.

## Styleframes and design system

A styleframe is a still finished to final render quality. Three to six frames should cover title, typical scene, data scene, lower third and end card. Approval locks fonts with family, weights, type scale, line height and tracking plus tabular figures for data, colour as brand tokens with text pairs pre checked for contrast, a spacing and layout grid with safe areas, and motion tokens of 3 to 5 named easing curves and a duration scale with no ad hoc per element curves.

Safe areas for 16 to 9 are action safe 93 percent and title safe 90 percent under SMPTE ST 2046-1 and EBU R 95. At 1920 by 1080 title safe is 1728 by 972 with margins of 96 px left and right and 54 px top and bottom. Social vertical safe zones are stricter and override broadcast safe areas for those deliverables.

## Animatic

Cut storyboard panels to the recorded or scratch voice at real duration with temp music and effects. The agent shortcut that preserves the gate is rendering the actual Remotion composition with styleframe stills, final timing and scratch audio at low resolution as a timing render, and getting approval on that file.

## Asset preparation

Keep vector assets as SVG, images at at least twice display size, video normalised to the composition fps, resolution and codec in an ffmpeg pre pass, audio as 48 kHz WAV masters, and fonts loaded explicitly. Use disciplined naming and versioning, and give every asset a rights and provenance note. Fetch official logos from brand sources and real captures for named repos and tools, following the presenter editor rules already proven in the Agent Video Editor system.

## Animation production passes

Pass one is blocking with pose to pose key states. Pass two is easing and springs. Pass three is secondary action, follow through and stagger. Pass four is sound sync hits. Review at full speed, frame step entrances and exits, and check stills at hero frames against approved styleframes.

## Directive rules

Create the directive after transcription and before motion design. Group words into complete semantic beats, mark each beat role, decide whether the beat benefits from visuals, and select exactly one primary treatment per interval. Define on screen copy, layout, reveal timing, exit timing and the spoken payoff word for each beat. Times are in source seconds, finite, non negative, ordered and within source duration, and beats must not overlap. Overlay layouts must not intersect protected regions. Reveal events must fall inside their beat. An unresolved ambiguity sets approval status to pending and rendering must stop. Also write a director treatment explaining visual rhythm, why full screen moments were selected, how presenter visibility is protected, and what remains intentionally clean. Validate every directive with scripts/validate_directive.py before execution.

Validation contract (v1.1). The validator runs in two stages. Draft mode (--draft) applies the schema gate only and prints VALID (DRAFT - schema only, NOT render permission). Strict mode applies the schema gate plus the render-ready gate and is the only mode that permits rendering. Exit codes are 0 valid, 1 invalid with handled coded errors and never a raw traceback, 2 tool error.

Schema gate: top level object, version 1, project name, format object with positive integer width and height, finite positive fps, and an aspect string consistent with the dimensions. NaN and Infinity are rejected at JSON parse time and booleans are never numbers. Every beat is an object with a unique id, finite ordered non-overlapping start and end inside the source duration, a minimum 0.4s hold, a role from the fixed set (hook, context, problem, promise, reveal, definition, process, proof, reassurance, transition, cta), a treatment from the fixed set (CLEAN_PRESENTER, OVERLAY_CARD, FULLSCREEN_MOTION, PRESENTER_INSET, SELECTIVE_TEXT, TRANSITION, KINETIC_TYPE, DATA_SCENE, CALLOUT, LOWER_THIRD, TITLE, END_CARD), and transition tokens from the fixed set (hard-cut, fade, fade-up, fade-rise, spring-pop, slide-fade, slide-up, slide-from-right, slide-from-top, slide-from-bottom, wipe-from-right, wipe-from-left, wipe-right, dissolve, zoom-punch, whip-pan, fade-to-endcard, none). LOWER_THIRD beats hold at least 3.0s.

Render-ready gate: approval.status must be exactly approved with zero ambiguities, and source.path must exist as a readable video whose ffprobe duration matches source.duration_s within max(0.5s, 2 percent).

Layout is required for every treatment except CLEAN_PRESENTER and TRANSITION, must be finite and positive, and must sit fully inside the canvas (off-canvas entrances are animation, not layout). Protected region collisions use an AABB rule with an explicit threshold: a layout fails when the overlap reaches 50 percent of the layout area or 50 percent of the protected region area. A deliberate exception sets allow_protected_overlap true on the beat with the reason in the brief and is always reported. Static rectangles never track a moving face, so frame inspection stays mandatory. Every reveal_sync element must be declared in the same beat on_screen_copy list and its time must fall inside the beat.
