# Platform, Retention and Accessibility

Confidence note is essential. YouTube does not publish retention benchmarks, loudness targets or social safe zone pixels as official specs in the sources found. The retention and safe zone numbers here are convergent practitioner and third party heuristics. Use them as editing heuristics and validate against each channel own YouTube Studio retention graph, which is the authoritative per channel source. Never quote a heuristic lift as a client guarantee.

## Retention editing

- Viewers decide to stay or swipe in about 1.5 to 3 seconds on short form, and about 50 to 60 percent of total drop off in analysed Shorts samples happened in the first 3 seconds.
- Long form first 3 seconds set the ceiling, and about 70 percent still watching at 0.30 is a healthy practitioner benchmark. Falling to about 50 percent by 0.30 rarely recovers.
- Stack the hook in three layers at once as a visual pattern interrupt, a spoken promise with a specific payoff and stakes, and on screen text stating the stakes. Put no logo sting, greeting or slow ramp before the hook.
- Pattern interrupts reset attention through a jump cut, punch in zoom, B roll cutaway, graphic, sound hit, or angle and scale change. Change the visual every 2 to 4 seconds in short form, and interrupt every 10 to 15 seconds of talking head in long form.
- Short form pacing cuts pauses above about 0.3 seconds and filler words while leaving a breath after punchlines. Long form allows pauses to breathe for emphasis and comedy, and uses chapter structure for re engagement.
- Short form captions are burned in and animated because a large share of social viewing is muted. Every short form deliverable must be fully comprehensible muted, and every hook must work as text plus image alone.
- Diagnose retention by graph shape. A cliff at 0 to 3 seconds is a hook problem, a mid video cliff is a specific moment to cut, and a slow bleed is a cut frequency or value density problem.

## Platform format specifics

The common vertical master is 1080 by 1920 at 9 to 16.
- Meta Reels ads guide figures keep critical content out of the top 14 percent at about 270 px, the bottom 35 percent at about 672 px, and 6 percent on each side at about 65 px at 1080 by 1920. The profile grid crops covers toward 3 to 4 and 4 to 5, so cover titles belong in the centre.
- TikTok approximations are top about 130 to 160 px, bottom about 350 to 440 px growing with caption length, and a right action rail of about 140 to 200 px.
- For a cross platform single file keep every word and logo inside roughly the centre 856 by 1094 px region. The better route is per platform variants from the same composition with safe zone as a prop, because the code pipeline makes variants cheap.
- Reels feed preview crops 9 to 16 toward 4 to 5, so centred faces and titles survive both.
Safe zone pixel values change with app updates and are reverse engineered approximations except for the Meta ads guide percentages. Ship overlay templates as updatable assets, not constants buried in code, and re check in the app preview before a major launch.

## Accessibility hard rules

- Captions are required for prerecorded audio in synchronised media under WCAG 1.2.2 Level A. Quality limits from Netflix and BBC timed text guides are at most 42 characters per line with BBC broadcast at 37, at most 2 lines, at most 20 characters per second for adults and 17 for children, BBC reading rate 160 to 180 words per minute, and minimum cue duration 5/6 seconds with maximum 7 seconds for standard timed text. Social caption pages are shorter by design.
- Contrast under WCAG 2.2 AA is at least 4.5 to 1 for normal text, at least 3 to 1 for large text at 18 pt or 24 px or 14 pt bold, and at least 3 to 1 for meaningful graphics and UI parts. For burned in captions over moving footage a solid or semi opaque background pill or heavy stroke is the reliable way to guarantee the ratio on every frame.
- Photosensitivity under WCAG 2.3.1 Level A means nothing may flash more than 3 times in any 1 second period unless below the general and red flash thresholds. Default to no strobe, never flash saturated red, and count all flashing sources together including cuts to contrasting frames, glitch transitions, sticker pulses and lightning visuals. Check suspect sequences with a flash analyser in QC, and use an on screen warning only as a last resort, never as a licence to exceed the threshold.
- Motion sensitivity means honouring reduced motion principles for UI and screen content, avoiding sustained spinning, rapid zooms and shaky effects that induce vestibular discomfort, and never encoding essential information in motion alone. Always pair motion with text or a static state.
