# Export Presets and Quality Control

## Export presets

Container for YouTube is MP4 with moov atom at front, video H.264 High Profile progressive with closed GOP at half the frame rate and CABAC and VBR at 4.2.0, audio AAC LC at 48 kHz with stereo at 384 kbps, colour BT.709 SDR, and upload at the recorded frame rate. YouTube re encodes everything, and the table is a quality reference rather than a hard limit.

- YouTube long form 1920 by 1080 at 24 to 30 fps is 8 Mbps, and at 48 to 60 fps is 12 Mbps.
- YouTube long form HDR at 1080p is 10 Mbps, and 15 Mbps at 60 fps.
- YouTube 1440p at 30 fps is 16 Mbps and at 60 fps is 24 Mbps. Uploading a 1080p master at 1440p is a common quality tactic.
- YouTube 4K at 24 to 30 fps is 35 to 45 Mbps and at 48 to 60 fps is 53 to 68 Mbps.
- Shorts, Reels and TikTok master is 1080 by 1920 at 9 to 16, 30 fps, H.264 plus AAC at 48 kHz, and 10 to 16 Mbps as a working range. Export clean with no rival platform watermark per platform.
- Broadcast EU follows the broadcaster spec sheet which overrides everything here, often with a ProRes or DNx mezzanine.
- Alpha overlay and mezzanine uses comp size with ProRes 4444 or PNG sequence and never H.264.

## Quality control checklist

Run this gate on the final encoded file and attach frame grabs and a loudness report to the deliverable.

1. Frame inspection. Step through every entrance, exit and transition frame by frame. Grab stills at the start, the hook frame, every scene hero frame and the end card, and compare to styleframes. Check for blank or loading frames, font fallbacks, clipped text and one frame pops.
2. Safe margins. Overlay title safe at 90 percent and the target platform social safe zone template. Keep text, logos and CTAs out of UI bands.
3. Caption accuracy. Do a human pass against audio for names, numbers and low confidence words. Check characters per line, line count, reading speed, spelling, and sync within 1 to 2 frames. Confirm captions do not cover lower thirds or callouts.
4. Loudness and true peak. Measure the full programme on the final encoded file. Integrated loudness must sit within tolerance of target and true peak at or below ceiling.
5. Technical probe. Confirm resolution, fps, codec, pixel format, colour space, moov at front for MP4, full end to end playback, no frozen frames or audio dropouts, and alpha actually present for overlay deliverables: the pixel format must carry an alpha marker (yuva, rgba, bgra and relatives) or, for VP8/VP9, the alpha_mode=1 tag - and the decoded alpha plane must actually vary, because a constant-opaque alpha is the "composites as a black box" failure.
6. Accessibility. Check contrast, run a flashing scan at or below 3 flashes per second, sanity check reduced motion for UI mockups, and confirm sidecar captions exist where the platform supports them.
7. Content and legal. Check claims, prices, spelling of names and titles, music and asset licences, and platform policy including rival watermarks.

Use templates/qc-checklist.md for the sign off record. scripts/qc_probe.py is an authoritative automated gate, not a print-only probe: run it on the final encoded file with a per-deliverable --spec and save the --report JSON. Starter specs ship in templates/ (delivery-spec-youtube-1080p.json, delivery-spec-vertical-1080x1920.json, delivery-spec-alpha-overlay.json). The default social profile (audio required, minus 14 LUFS plus or minus 1.5, true peak at or below minus 1.0 dBTP) applies without a spec. Missing required audio fails as AUDIO_STREAM_MISSING, digital silence fails as AUDIO_SILENT, and out-of-spec loudness, true peak, dimensions, frame rate (tolerance 0.01, VFR detected), codec, pixel format, profile, field order, colour tags, bit-rate range, audio codec/channels/sample rate, duration, required alpha, or moov placement each fail with a nonzero exit. QC gate contract (v1.2): spec keys are whitelisted and type-checked - an unknown key or a wrongly-typed value is a tool error (exit 2), never silently ignored; a spec that produces zero checks FAILS instead of passing vacuously; the moov check streams box headers (no whole-file load) across .mp4/.mov/.m4v and a missing moov is a FAIL; alpha_required checks both the format (pixel format or VP8/VP9 alpha_mode tag) and the content (the decoded alpha plane must drop below 90 percent of full scale somewhere - some ProRes encoders store opaque alpha at 3760 of 4095, so the comparison is against 90 percent, not the exact maximum). Exit 2 means the probe itself failed (missing tools, bad spec, unwritable report) and an ERROR report is written when --report is given. Human-only items in this checklist (caption accuracy, content and legal, visual taste) are recorded as requiring sign-off and are never auto-passed. Use scripts/sample_frames.py for deterministic frames plus a contact sheet; with --directive it also samples every beat start, reveal time and beat end.
