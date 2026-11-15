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

Create the directive after transcription and before motion design. Group words into complete semantic beats, mark each beat role, decide whether the beat benefits from visuals, and select exactly one primary treatment per interval. Define on screen copy, layout, reveal timing, exit timing (the beat's exit_s field) and the spoken payoff word (the beat's spoken_text field) for each beat. Times are in source seconds, finite, non negative, ordered and within source duration, and beats must not overlap. Overlay layouts must stay clear of protected regions under the collision rule below. Reveal events must fall inside their beat. An unresolved ambiguity sets approval status to pending and rendering must stop. Also write a director treatment (template: templates/director-treatment-template.md) explaining visual rhythm, why full screen moments were selected, how presenter visibility is protected, and what remains intentionally clean. Validate every directive with scripts/validate_directive.py before execution.

## Routes (v1.2)

The four production routes differ by source and length. Fast intro: a title or bumper of at most 15s, usually graphics-only (source.kind "none"). Short form: at most 90s vertical or square social video over footage or graphics. Long form: over 90s, footage-led, chaptered beats. Graphics only: no camera footage at all - lyric videos, logo animation, explainers built from stills and type; the source is kind "audio" (a song or voice track) or kind "none" with timeline.duration_s. Presenter treatments (CLEAN_PRESENTER, PRESENTER_INSET, OVERLAY_CARD, SELECTIVE_TEXT) are only legal on the footage routes.

Validation contract (v1.2). The validator runs in two stages. Draft mode (--draft) applies the schema gate only and prints VALID (DRAFT - schema only, NOT render permission). Strict mode applies the schema gate plus the render-ready gate and is the only mode that permits rendering. Exit codes are 0 valid, 1 invalid with handled coded errors and never a raw traceback, 2 tool error (missing directive file, unknown flag, ffprobe unavailable). --report PATH writes the machine-readable result including warnings.

Schema gate: top level object, version the integer 1 (booleans rejected), project name, format object with positive EVEN integer width and height, finite positive fps from the standard set, and an aspect string consistent with the dimensions within 0.005. NaN and Infinity are rejected at JSON parse time and booleans are never numbers. Unknown keys are errors everywhere (a typo can no longer disable a check). Every beat is an object with a required unique string id, finite ordered non-overlapping start and end, a minimum 0.4s hold compared in frames (so exactly-legal durations pass), a role from the fixed set (hook, context, problem, promise, reveal, definition, process, proof, reassurance, transition, cta), a treatment from the fixed set (CLEAN_PRESENTER, OVERLAY_CARD, FULLSCREEN_MOTION, PRESENTER_INSET, SELECTIVE_TEXT, TRANSITION, KINETIC_TYPE, DATA_SCENE, CALLOUT, LOWER_THIRD, TITLE, END_CARD), and transition tokens from the fixed set. Entrance tokens (how one graphic enters): fade, fade-up, fade-rise, spring-pop, slide-fade, slide-up, slide-from-left, slide-from-right, slide-from-top, slide-from-bottom. Scene tokens (how one shot becomes the next): hard-cut, none, dissolve, wipe-from-right, wipe-from-left, wipe-right, zoom-punch, whip-pan, fade-to-endcard, morph, match-cut, flip, clock-wipe. The validator accepts the union in either transition field; the grouping is a directing convention. LOWER_THIRD beats hold at least 3.0s. On-screen copy is checked for reading speed: above 40 chars/s is an error, above 20 chars/s a warning. Gaps over 0.5s between beats warn, because every interval should carry exactly one treatment.

Render-ready gate: approval.status must be exactly approved with zero ambiguities and a named approved_by (approved_at should be recorded; its absence warns). The source is probed: kind video requires a video stream, kind audio an audio stream, kind none takes timeline.duration_s. The probed duration must match the declared duration within about one frame, format.fps must match the source frame rate, and every beat must end inside the probed timeline. A relative source.path resolves against the directive's own folder.

Layout is required for every treatment except CLEAN_PRESENTER and TRANSITION, is type-checked for every treatment, must be finite and positive, and must sit fully inside the canvas (off-canvas entrances are animation, not layout; declare an intentional overscan in the beat's rationale text). Protected region collisions use an AABB rule: a layout fails when the overlap reaches 10 percent of the protected region area or 50 percent of the layout area, and on ANY overlap of a region flagged critical. A deliberate exception sets allow_protected_overlap to the boolean true on the beat AND a non-empty overlap_reason string on the same beat; every applied override is printed as a WARN [PROTECTED_OVERRIDE] line and recorded in the --report JSON. Static rectangles never track a moving face, so frame inspection stays mandatory. Every reveal_sync element must be declared in the same beat on_screen_copy list (reveal_sync without on_screen_copy is an error) and its time must fall inside the beat.
