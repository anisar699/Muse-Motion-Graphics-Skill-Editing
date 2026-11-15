# Motion Principles, Easing, Durations, Frame Rates and Motion Blur

Researched 15 Nov 2026. Numbers are professional conventions or standards as labelled. Full sources in research-sources.md.

## The 12 principles translated to motion graphics

1. Squash and stretch. Scale deformation on impact or landing while preserving volume. Subtle in corporate work at about 2 to 8 percent, exaggerated in playful work. Use for logos, balls, cards and buttons.
2. Anticipation. A small counter move before the main move. Working rule is about 10 to 20 percent of the main action duration, or 5 to 10 percent of travel distance over 3 to 6 frames at 30 fps. This is a practitioner rule, not a Disney published number.
3. Staging. One clear idea per moment. In editing terms, one primary animating element per beat, never two competing animations at once.
4. Straight ahead versus pose to pose. Pose to pose is the blocking workflow of styleframe, key poses, then in betweens, which in code means defining key states in interpolate ranges first. Straight ahead is procedural physics such as springs, noise and particles for organic motion.
5. Follow through and overlapping action. Parts stop at different times. The main element lands and secondary elements such as underline, icon and shadow settle 2 to 6 frames later. Implement as staggered delays.
6. Slow in and slow out. Easing is the single highest impact principle for motion graphics. Real objects accelerate and decelerate, and linear motion reads as robotic.
7. Arcs. Natural paths are curved. Use bezier motion paths or add a secondary axis offset to a straight move.
8. Secondary action. A subordinate gesture that reinforces the main one, such as a checkmark drawing while a card scales in. It must not compete with the primary action.
9. Timing. Frame count sets weight and mood. The same move at 8 frames feels snappy and energetic, at 30 frames slow and deliberate. Heavy objects need more frames, more anticipation and more follow through.
10. Exaggeration. Push beyond reality for clarity through overshoot, slam and elastic, scaled to brand tone. Near zero for news and finance, high for social entertainment.
11. Solid design. Consistent volume, perspective, spacing and design system while things move. In 2.5D and 3D, objects must not reveal they are flat cards.
12. Appeal. Clean shapes, rhythmic durations, deliberate asymmetry and contrast. The test is whether a still styleframe is appealing.

Priority order for this skill is easing, timing, anticipation, follow through and overlap, and staging. Squash and stretch and exaggeration are seasoning.

## Easing library

A cubic bezier has fixed endpoints 0,0 and 1,1. The y value may go below 0 for anticipation or above 1 for overshoot, and that is exactly how overshoot is made.

Direction rule from Material Design, convergent across Material 3, Carbon and Fluent:
- Entering uses decelerate or ease out, arriving fast and settling gently.
- Exiting uses accelerate or ease in, starting gently and flying off. Exits are also shorter.
- Moving on screen uses standard or ease in out.
- Linear is only for continuous loops, spinners, marquees, progress and time driven values.

Material Design 3 tokens:
- standard is 0.2, 0, 0, 1 for most transitions.
- standard decelerate is 0, 0, 0, 1 for entering.
- standard accelerate is 0.3, 0, 1, 1 for exiting.
- emphasized decelerate is 0.05, 0.7, 0.1, 1.0 for expressive entering.
- emphasized accelerate is 0.3, 0, 0.8, 0.15 for expressive exiting.
- linear is 0, 0, 1, 1 for loops only.

Named curves for Remotion Easing.bezier:
- easeOutCubic 0.33, 1, 0.68, 1 is the balanced safe default entrance.
- easeOutQuart 0.25, 1, 0.5, 1 is snappy.
- easeOutQuint 0.22, 1, 0.36, 1 is very snappy and decisive.
- easeOutExpo 0.16, 1, 0.3, 1 is dramatic and premium, and is the house workhorse.
- easeInCubic 0.32, 0, 0.67, 0 is the balanced exit.
- easeInOutCubic 0.65, 0, 0.35, 1 is the balanced on screen move.
- easeOutBack 0.34, 1.56, 0.64, 1 overshoots past the target then settles. Use for logos, pop ins and success states. The 1.56 is the overshoot.
- Avoid generic CSS ease 0.25, 0.1, 0.25, 1 as a deliberate choice.

Springs versus bezier:
- A spring is defined by mass, stiffness and damping and has no fixed duration. It settles when physics settles. Use measureSpring to know its length in frames, or force a duration to stretch it to an exact slot.
- Use springs for organic entrances, overshoot and follow through.
- Use bezier interpolate when duration must hit a beat or word exactly, and for loops, progress and data values.
- Remotion presets are damping 200 for smooth no bounce, damping 12 to 15 for playful bounce, and damping 20 with stiffness 200 and mass 0.8 for snappy.

Overshoot, anticipation and follow through recipes:
- Overshoot uses easeOutBack or a spring with damping 12 to 20. Keep overshoot distance about 2 to 10 percent of travel for professional work. More reads as cartoon.
- Anticipation uses a reverse move of about 5 to 10 percent of travel over 3 to 6 frames at 30 fps, or a negative y ease in back curve.
- Follow through staggers secondary elements by 2 to 4 frames per element. Kinetic type bounce stagger is 2 to 4 frames per character, wave stagger is 3 to 5 frames per character.

## Duration table at 30 fps

Material Design 3 duration tokens are short 50 to 200 ms, medium 250 to 400 ms, long 450 to 600 ms, and extra long 700 to 1000 ms. Duration scales with distance and size moved. Above about 500 ms on a phone feels sluggish except for full screen, first run or celebration moments.

- Micro fade or icon state is 100 to 200 ms, or 3 to 6 frames.
- Snap wipe or accent reveal is about 270 ms, or 8 frames, with branded wipes at 8 to 12 frames.
- Crossfade or dissolve is 6 to 20 frames. Prefer 6 to 12 frames for social, because dissolves are the first thing to shorten.
- Lower third entrance is 500 ms or 15 frames. Hold at least 3 seconds or 90 frames, with a typical total of 3 to 5 seconds. Exit faster than entrance.
- Standard entrance for a title, card or chart is 250 to 500 ms, or 8 to 15 frames. Stagger children 2 to 5 frames apart.
- Any exit is 150 to 300 ms, or 5 to 9 frames, at about 60 to 75 percent of its entrance duration with ease in.
- Logo reveal is 1.5 to 2 seconds of animation within a 2 to 4 second sting, or 45 to 60 frames.
- Scene transition is 200 to 500 ms, or 6 to 15 frames. Use 20 to 30 frames only for a slow mid show branded wipe.
- On screen text hold is governed by reading time. Allow at least 0.33 seconds per word or stay at or below 20 characters per second. Never let a hold be shorter than entrance plus exit.

Choreography rules are stagger rather than synchronise, asymmetric enter and exit, one primary motion per beat, and a still hold after landing.

## Frame rates

- 24 fps is cinematic, with 23.976 for NTSC derived delivery.
- 25 fps is PAL region broadcast legacy.
- 30 fps is the TV, web and social default and the Remotion conventional default.
- 48, 50 and 60 fps are for gaming, sport, fast UI and screen capture and slow motion source. They double render time and bitrate needs.
- 12 fps on twos is a deliberate stylised stepped look.
- Never change fps by re timing a composition casually, because every frame based duration changes meaning. Store durations in seconds and convert with seconds times fps in code.

## Motion blur

A film frame is a sample of time. At 24 fps each frame samples 1/24 second, a moving object occupies multiple positions in that time, and so it blurs. Without blur, computer animation strobes. Source is Adobe After Effects documentation, read live during research.

- Shutter angle controls blur amount. 90 degrees at 24 fps equals an exposure of 1/96 second.
- 180 degrees is the cinematography standard and the right default for graphics that must match live footage, giving a shutter speed of twice the frame rate such as 1/48 at 24 fps.
- 270 to 360 degrees is stylised heavy smear for sport and titles.
- 45 to 90 degrees or less is crisp for UI and data visualisation where blur would destroy legibility.
- In code there is no true shutter. Emulate with Remotion motion blur or trail techniques, ffmpeg tmix or minterpolate for footage, or directional blur proportional to per frame displacement. Disable emulation on text that must be read and on data.
