# Remotion Code Patterns, Alpha and Performance

## Determinism rule

A component is a pure function of frame number to image. Remotion renders frames in parallel across browser tabs that do not share state, so anything not derived from useCurrentFrame such as CSS transitions, timers, Date.now or uncontrolled Math.random will flicker, desync or differ per machine. This was read live on the Remotion flickering documentation during research.

## Animation rules

- Derive all animation from useCurrentFrame and useVideoConfig, where frame is local inside each Sequence and starts at 0.
- Use interpolate with easing and with extrapolateLeft and extrapolateRight both set to clamp. The default extrapolation extends and silently overshoots bounded values such as opacity.
- Write timing in seconds as values such as 0.5 times fps, never as bare frame numbers without a seconds comment.
- Use spring for organic motion and map its 0 to 1 output through interpolate to pixels or degrees. Use damping 200 for smooth no bounce, damping 20 with stiffness 200 and mass 0.8 for snappy, damping 8 to 15 for bouncy, and damping 15 with stiffness 80 and mass 2 for heavy. Use measureSpring for exact settle length and per element frame delays for staggers.
- Prefer inline interpolate in style with individual scale, translate and rotate properties over composed transform strings, so keyframes stay editable in Remotion Studio.
- Register every deliverable as a Composition with id, component, durationInFrames, fps, width, height, defaultProps and calculateMetadata for data driven duration and size. Build scenes with Sequence and Series, transitions with TransitionSeries, and shared elements such as lower third, captions and end card as parametrised components driven by a design token file and a schema for props.
- Use seeded random only. Load media with Img, Video or OffthreadVideo and Audio components that block for assets. Load async data and fonts with delayRender and continueRender, and load fonts at module top level with narrowed weights and subsets because a bare load can hit the delayRender timeout.
- Derive durations from caption JSON or a beat grid through calculateMetadata, so a new voiceover re times the whole composition instead of requiring hand edits.

## Performance for fast renders

- Set concurrency near CPU cores by default and benchmark per machine. Lower it under memory pressure from large embedded videos.
- Use JPEG frames for opaque compositions because they render faster than PNG. Use PNG only when alpha is needed.
- Prefer OffthreadVideo or the current frame exact media components for renders, following the installed version docs.
- Keep frames cheap with a target below 100 ms per frame. Pre render static blurred backgrounds to images, memoise frame independent computation, and keep the DOM per frame lean, because full screen blurs, shadows and filters are the usual bottleneck.
- Draft at scale 0.5 for timing and animatic approvals, render final at full scale, and re render only a fixed range with the frames option after a local fix.
- Version lock all @remotion packages to the exact same version and render through the CLI with an explicit props file.

## Transparency and alpha workflow

Alpha must survive every link of source background, frame image format, codec, pixel format and container. Any wrong link silently yields a black or opaque rectangle.

Official Remotion recipes read live during research:
- For WebM in browsers use PNG frames with codec VP8 or VP9 and pixel format yuva420p.
- For ProRes in editors use PNG frames with codec prores, profile 4444 or 4444-xq, and pixel format yuva444p10le.
- Set no background on the root and confirm transparency with the Studio checkerboard.

Pitfalls:
- JPEG frames have no alpha and are the number one silent failure.
- H.264 and MP4 cannot carry alpha at all.
- Transparent WebM on Lambda can flicker at chunk boundaries because alpha depends on previous frames while chunks render independently. Prefer ProRes on Lambda, render WebM in one local pass, or raise frames per chunk.
- A one character pixel format error such as yuv444p10le instead of yuva444p10le produces a file that looks fine on black and composites as a black box.
- ProRes 4444 is large at roughly 5 MB per second for a sparse caption overlay and 15 MB per second for a full phone overlay in one production report, so budget storage and transfer.

Proven lesson from the Agent Video Editor test on 2026-11-15 in this workspace is that Remotion 4.0.543 direct video renders in prores and vp9 silently dropped alpha despite PNG image format. The working route was a PNG sequence with the sequence flag, then ffmpeg prores_ks 4444, verified frame by frame. Pixel-format reporting needs care (corrected v1.2): the ffmpeg ProRes decoder reports 4444 streams as yuva444p12le regardless of whether the encoder was fed yuva444p10le or yuva444p12le, because ProRes 4444 stores 12-bit components. So an ffprobe reading of yuva444p12le does not tell you which input format the encoder used, and a QC expectation of the exact string yuva444p10le will always fail. State which encoder route a deliverable used when reporting, and never spec an exact yuva444p10le probe result. Use the PNG sequence route as the default safe route in Muse Motion, then verify the alpha plane on the final file.

Alpha route commands (v1.2 - these were described but never written down):
ProRes 4444 master from a PNG sequence:
ffmpeg -framerate 30 -i frames/frame_%04d.png -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -vendor apl0 out.mov
VP9 alpha WebM for browsers from a PNG sequence:
ffmpeg -framerate 30 -i frames/frame_%04d.png -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 18 -auto-alt-ref 0 out.webm
Verify either output with scripts/qc_probe.py and a spec with overlay.alpha_required true; note ffprobe shows VP9 alpha files as yuv420p with TAG alpha_mode=1, which the QC gate accepts.

PNG sequence is the most portable workflow. Render the sequence to numbered PNG frames, QC individual frames, composite in ffmpeg or hand the sequence to any editor, and re render only the fixed frames after a local defect.


## Canonical beat component and font loading guardrail (v1.1)

Block the render until custom fonts are loaded, especially for RTL and Indic scripts (Urdu, Arabic, Devanagari), where a fallback font changes line breaks and can overflow a locked layout. Use @remotion/google-fonts or an explicit delayRender and continueRender pair, and never start a render on a font timeout fallback for locked text.

```tsx
import {Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export const BeatCard: React.FC<{title: string}> = ({title}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const opacity = interpolate(frame, [0, 0.35 * fps], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const scale = spring({frame, fps, config: {damping: 20, stiffness: 200, mass: 0.8}});
  return <div style={{opacity, scale: String(scale)}}>{title}</div>;
};
```
