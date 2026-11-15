# Muse Motion QC Checklist

- Project:
- Final file:
- Date and checker:

## Frame inspection
- Hook frame checked
- Every scene hero frame checked against styleframes
- Every entrance, exit and transition stepped frame by frame
- No blank frames, font fallbacks, clipped text or one frame pops

## Safe areas and layout
- Title safe overlay checked for 16 to 9
- Platform safe zone overlay checked for vertical
- No text, logo or CTA in platform UI bands
- Presenter face, eyes, mic and gesture corridor clear

## Captions
- Human pass against audio done
- Names, numbers and low confidence words checked
- Line length, line count and reading speed within limits
- Captions do not cover lower thirds or callouts
- Sidecar SRT and VTT emitted where supported

## Audio
- Loudness measured on final encoded file, value:
- True peak measured on final encoded file, value:
- Target for this destination:
- Sound hits within one frame of visual landings

## Technical
- ffprobe resolution, fps, codec, pixel format and colour recorded
- MP4 moov atom at front confirmed where required
- Full file plays end to end with no frozen frames or dropouts
- Alpha plane confirmed for overlay deliverables

## Accessibility and legal
- Contrast at or above 4.5 to 1 for normal text
- Flashing at or below 3 flashes in any 1 second
- Claims, prices and name spellings checked
- Music and asset licences recorded

## Verdict
- Pass or fail:
- Defects found and fixed:
- Not verified, and why:
