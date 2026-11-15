# Muse Motion Changelog

## v1.1 - 2026-11-15

Fixes from two independent developer audits of v1.0. Every finding was re-verified against the v1.0 files before fixing; the auditors' own 18-case regression suite went from 16 failures on v1.0 to 18 of 18 passing on v1.1.

- validate_directive.py rewritten as a two-stage gate. Schema gate plus render-ready gate: approval must be approved with zero ambiguities (MM-001), source media must exist, probe as video, and match the declared duration (MM-002), layouts are required where the treatment needs them and must sit inside the canvas (MM-005), protected regions are collision-checked with an explicit 50 percent AABB overlap threshold and a documented override flag (MM-006), format, fps, aspect, treatment, role and transition tokens are validated against fixed sets (MM-007), malformed structures return handled INVALID errors with rule codes and never a traceback (MM-008), NaN and Infinity are rejected at parse time and booleans are never numbers (MM-009), and reveal_sync elements must be declared in on_screen_copy with times inside the beat (MM-010). A --draft mode validates schema only and never counts as render permission.
- qc_probe.py rewritten as an authoritative delivery gate (MM-003, MM-004, MM-011). It accepts a per-deliverable --spec, writes a machine-readable --report JSON, and exits 0 PASS, 1 FAIL, 2 tool error. Missing required audio fails as AUDIO_STREAM_MISSING, digital silence fails as AUDIO_SILENT, and loudness target and tolerance, true peak ceiling, dimensions, frame rate, codec, duration, required alpha pixel format, sample rate, and MP4 moov placement are all enforced.
- New scripts/sample_frames.py extracts deterministic hook, quarter, hero, three-quarter and end frames plus a contact sheet and manifest (partial automation for MM-012; visual judgement still requires human sign-off).
- SKILL.md gained standard YAML frontmatter for portable skill loaders (skill.yaml remains the Muse metadata source), the treatment list now matches the validator's 12 uppercase tokens exactly, and the role list matches the validator's lowercase tokens.
- ffmpeg reference gained the format=auto overlay chain with +faststart and a sidechaincompress voice-ducking pipeline.
- Remotion reference clarified that yuva444p10le (Remotion ProRes route) and yuva444p12le (ffmpeg prores_ks route) belong to different encoders, and gained a canonical TypeScript beat component plus a font-loading guardrail for RTL and Indic scripts.

Not fixed, deliberately:

- The connector links in SKILL.md use this workspace's standard paths. They are correct for Muse; other environments should map them to their own Drive and workspace tools (see the portability note in README.md).
- No complete Remotion sample project is bundled yet (MM-013 stays open as a known limitation). The gates, frame sampler, and real renders produced in the workspace are the current evidence; the package does not claim archive-level render proof.
- Automated visual regression beyond frame sampling (MM-012 remainder) stays a human sign-off step by design.
