# Muse Motion

Professional motion graphics video editing skill for Muse.

Install by placing the `muse-motion` folder under `~/workspace/custom-skills/` so the path is `~/workspace/custom-skills/muse-motion/SKILL.md`, then start a new conversation and ask Muse to edit a video. Muse will load this skill for motion graphics work.

Contents: SKILL.md is the main workflow. The references folder holds the researched detail on principles and easing, the full element taxonomy, workflow and directive rules, Remotion code patterns, ffmpeg and audio, export presets and QC, platform retention and accessibility, and sources. The templates folder holds a brief, an editorial directive JSON, a QC checklist, a director treatment, and three delivery-spec JSONs. The scripts folder holds a directive validator, a final file QC probe, and a frame sampler, all tested locally. The tests folder holds the shipped regression suite; requirements.txt lists the runtime dependencies.

Built 2026-11-15 from a dedicated research report plus the proven Agent Video Editor workflow already tested in this workspace, including the PNG sequence alpha lesson.


## Version 1.2 (2026-11-15)

See CHANGELOG.md for the full fix list from the third independent developer audit, of v1.1. The package now ships its own regression suite (tests/test_muse_motion_regression.py, 28 cases, all passing on v1.2), and the v1.0 auditors' 18-case suite still passes 18 of 18.

## Version 1.1 (2026-11-15)

See CHANGELOG.md for the full fix list from the two independent developer audits of v1.0. The auditors' regression suite passes 18 of 18 on v1.1 (it failed 16 of 18 on v1.0).

Portability note: SKILL.md carries standard YAML frontmatter so generic skill loaders can parse it, and skill.yaml remains the metadata source inside Muse. The connector links in SKILL.md point at this workspace's standard locations; in another environment, map them to that environment's Drive and workspace tools instead of treating the paths as broken.

Licence note: this package is the author's work (see LICENSE). Remotion itself is free for individuals and small teams but requires a paid company licence for larger for-profit teams - check remotion.dev/license before using the Remotion route commercially at scale.

Known limitations, stated plainly: the package does not yet bundle a complete Remotion sample project or an automated visual-regression suite, and the directive model supports one source file per directive. Directive validation, delivery QC, and frame sampling are executable and tested; narrative truth, caption accuracy, visual taste, and moving-face protection remain human sign-off steps.
