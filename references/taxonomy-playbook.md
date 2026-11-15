# Taxonomy Playbook for All Motion Graphics Elements

Durations are at 30 fps unless stated. Each family gives what it is, the professional spec, and the code approach.

## 1. Kinetic typography and text animation

Text as the main actor through per character, per word or per line reveals, mask reveals, typewriter, slam at 8 to 12 frames per word, bounce with spring per character at 2 to 4 frames stagger, wave with sine offset at 3 to 5 frames stagger, depth type, text to shape morphs, and rhythm locked type timed to beats or word timestamps. Animate only words that carry meaning. In code, split the string into units and drive each unit with spring or interpolate with delay equal to index times stagger.

## 2. Title sequences and openers

Full screen titles, episodic openers and chapter cards. Structure is establish the styleframe world, build as elements assemble, hero title lock up, hold at least 1 second readable, then exit or cut on energy. Broadcast openers often run 5 to 30 seconds. Online openers should be at most 2 to 3 seconds or moved after the hook, because a long opener before the hook destroys retention.

## 3. Lower thirds

Animated identification band with name as the primary line, role or organisation as the secondary line, an optional context or source tag, and an accent bar. Entrance is about 15 frames with the bar first, the name at about 0.2 seconds, the title at about 0.4 seconds, and the accent drawing at about 0.6 seconds in one published template. Hold at least 3 seconds, total typically 3 to 5 seconds, with a quiet fade or slide exit. Keep inside title safe, and on vertical social keep above the platform caption band. Hierarchy of name over role over context is non negotiable.

## 4. Captions and subtitle animation

Accessibility captions are faithful synchronised text with no animation or a simple fade, delivered as sidecar SRT or VTT and or burned in. Social burned in captions are a different product with word by word karaoke highlight, pop or scale on the spoken word, and 1 to 3 words or short phrases per page in TikTok style. Build social captions from word level timestamps, group words into pages that fit the frame, use one Sequence per page, and highlight the word whose start and end contain the current time. Standard limits are at most 42 characters per line, at most 2 lines, and at most 20 characters per second for adults.

## 5. Callouts and annotations

Arrows, drawn circles and ellipses, highlight boxes, magnifier and zoom callouts, leader lines with labels, freeze frame annotations, and telestrator style drawing. Draw on in 200 to 400 ms, pulse once rather than continuously, hold while narration refers to the target, and fade out with the topic. The callout must point unambiguously, so animate the pointing end last and keep the label inside the safe area.

## 6. Logo animation and brand idents

A logo sting is 2 to 4 seconds as the standard social and brand length, with opening and closing bumpers at 5 to 8 seconds. Patterns are build or draw on of the mark, reveal by mask or light sweep, assembly from brand shapes, and morph from a product or letterform. The reveal animation is 45 to 60 frames, the clean lock up holds at least 0.5 to 1 second, and the audio sting hit lands on the lock up frame. Deliver a toolkit of sting, loop, static lock up, and alpha versions, not one file.

## 7. Transitions

Transitions are punctuation and should express the logical relationship between scenes.
- Hard cut is the default at 0 frames for energy, news and comedy timing, including cut on action and J and L cuts in the edit.
- Cross dissolve or fade is 6 to 20 frames for time passing, softness and memory.
- Wipe, push or slide is 8 to 12 frames for a snap and 20 to 30 frames for a slow branded move, for directional and list to detail moves.
- Whip pan with directional blur and whoosh is 6 to 12 frames for fast lateral energy with a hidden cut in the pan blur.
- Zoom punch in or seamless zoom through a point is 8 to 20 frames for scale change and detail reveal.
- Morph is 15 to 30 frames when one shape or object becomes another.
- Match cut is a 0 frame cut where the outgoing shape, position, colour or direction matches the incoming one. The setup lives in framing.
- Seamless mask pass through, luma matte, ink or liquid and object wipe is 10 to 25 frames.
- Glitch, distort, spin and dip to colour are 4 to 10 frames as genre punctuation, used sparingly within flashing limits.
In Remotion use TransitionSeries from @remotion/transitions with fade, slide, wipe, flip and clock wipe presentations and linear or spring timing.

## 8. Infographics and data visualisation

Bars and columns grow from the baseline, never from centre or top, with ease out or spring, and value labels count up in sync with bar length. The axis and scale must be honest with no truncated axis unless marked. Lines and areas draw on left to right in time order with a dot landing on the final point. Pie and donut sweep from 12 o clock or build by segment with stagger, and label after the segment lands. Counters count up over 0.5 to 2 seconds with ease out to the exact final value, never overshooting a data value, with tabular numerals and formatting fixed from frame 1 so width never jitters. Timelines and processes reveal steps locked to narration as the connector draws, then the node pops, then the label. Maps drop pins with spring, draw routes on, fill regions in narration order, and push the camera to the relevant area. Animation order equals reading order equals narration order, and chart junk never animates.

## 9. UI and screen mockup animation

Phone and browser frames, cursor moves on an arc path with ease in out, click ripple with squash on the target, tap and scroll simulation, typed text, and highlight of the narrated feature. Keep UI text at native sharpness, because fake blur destroys legibility. Animate real UI states with the durations in the motion reference. Cursor moves should take about 300 to 600 ms with a 150 to 250 ms pause before a click so viewers register the target. Capture real repo or product pages when a tool is named rather than drawing a fake interface.

## 10. Social media formats

Hooks with first frame text and a spoken promise, burned in captions, progress bars driven linearly from frame over duration, chapter and segment labels, stickers and emoji accents with spring pop and fast exit that never cover captions, memes with punch in zooms and reaction cutaways, and loop optimised endings where the last frame connects to the first. Aspect and safe zone specs live in the platform reference.

## 11. Explainer and whiteboard animation

Explainer scenes are script driven with icon and illustration builds and one idea per scene, typically 3 to 8 seconds per scene. Whiteboard uses hand and marker draw on timed to narration, stroke order following how a human would draw, and camera pans between drawing zones. In code use SVG stroke dash draw on with a hand image following the path head. Both live or die on the animatic, because timing to the voice is the product.

## 12. 2.5D parallax and camera moves

Split flat artwork into foreground, midground and background planes at different depths and move a virtual camera. Near layers move faster than far layers, and that differential is the depth. Illustrative pan speeds are foreground 100 percent, midground about 60 percent, and background about 30 percent of camera speed, tuned per scene as a practitioner illustration rather than a standard. Camera vocabulary is dolly and push in, pan, tilt, zoom, and crane or parallax truck. Add depth of field softening on far and near planes and scale change on push. Keep angles modest so flat cards never reveal themselves. In Remotion use absolutely positioned layers with translate and scale as a function of frame and depth factor, or CSS 3D and Three.js for true perspective.

## 13. 3D motion

True modelled 3D for product turntables, logo extrusions, camera fly throughs, lighting and material animation, and physics. In this stack use Three.js or React Three Fiber inside Remotion, or Blender renders composited through ffmpeg or PNG sequence. Modelling, lighting and render time dominate cost, so reserve 3D for hero moments such as product and logo and keep the rest 2D or 2.5D. Product standards are a 360 degree turntable in 4 to 8 seconds, exploded view, macro dolly across details, and hero light sweep.

## 14. Character animation basics

Keep characters simple and rigged from parts. Use squash and stretch on jumps and lands, anticipation before actions, follow through on hair, limbs and props, walk cycles with contact, down, passing and up poses at 8 to 12 frames per step at stylised rates, approximate lip sync only for explainers, and blink cycles every 2 to 5 seconds with eyes closed for 2 to 4 frames. Blinks and idle sway make a static rig feel alive. Default to limited animation with holds and strong poses rather than continuous mediocre movement, because full character performance is where flat code rigs most visibly trail dedicated puppet tools.

## 15. Product promo motion

Benefit led sequence of problem or context, product hero, feature callouts, UI in use, proof through data, and packshot with CTA hold. Use short benefit phrases at one per beat. Price and offer cards get the longest holds for reading time.

## 16. Music and lyric videos

Build the beat grid first by detecting BPM and downbeats, place cuts and type hits on beats and pickups, and sync kinetic lyric typography to vocal word timestamps from the same Whisper pipeline. Visual intensity follows song energy with restraint in verses and scale, colour and speed in choruses. Lyrics and master rights are a delivery gate.

## Element family to treatment mapping (v1.2)

The directive has 12 treatment tokens; the 17 families above map onto them as follows. 1 Kinetic typography: KINETIC_TYPE (or SELECTIVE_TEXT over footage). 2 Titles and openers: TITLE. 3 Lower thirds: LOWER_THIRD. 4 Captions: SELECTIVE_TEXT for burned-in pages over footage, KINETIC_TYPE full-frame. 5 Callouts and annotations: CALLOUT. 6 Logo animation and brand idents: TITLE (short brand beat, usually on the graphics-only route). 7 Transitions: TRANSITION beats, or the transition tokens on neighbouring beats. 8 Infographics and data: DATA_SCENE. 9 UI and screen mockups: FULLSCREEN_MOTION (full-frame capture) or OVERLAY_CARD (inset over a presenter). 10 Social formats: composed from the other treatments; hooks are a role, not a treatment. 11 Explainer and whiteboard: FULLSCREEN_MOTION. 12 Parallax and camera moves: FULLSCREEN_MOTION (the move is inside the scene). 13 3D motion: FULLSCREEN_MOTION. 14 Character animation: FULLSCREEN_MOTION. 15 Product promo: FULLSCREEN_MOTION or OVERLAY_CARD for price/feature cards. 16 Music and lyric videos: KINETIC_TYPE over kind "audio" or "none" sources. 17 Intros, outros, end screens and CTAs: TITLE for intros, END_CARD for outros and CTAs.

## 17. Intros, outros, end screens and CTAs

Online intros are 0 to 3 seconds or none before the hook. YouTube end screens run in the last 5 to 20 seconds, so keep that window visually clear for platform elements. In frame end cards hold a subscribe, next video or CTA lock up readable for at least 3 to 5 seconds with no new information competing. A CTA shows one action only, pops in with spring, and loops subtly at no more than one pulse per 2 seconds within flashing limits. On Shorts and Reels never place a CTA under the platform buttons.
