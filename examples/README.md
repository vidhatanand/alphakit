# Alphakit Examples

This folder is reserved for real Codex-generated black/white pair demos.

Accepted demo structure:

- `pairs/<demo>-black.png`: Codex-generated black-background source.
- `pairs/<demo>-white.png`: generated with the black image as reference input, changing only the background to white.
- `pairs/<demo>-green.png`: optional green-background third image, generated only after black/white `negative_diff_ratio` fails.
- `transparent/<demo>.png`: output from `scripts/alpha_from_black_white.py`.
- `transparent/<demo>.webp`: lossless WebP export with alpha.
- `reports/<demo>.json`: extraction profile, selected candidate, visual-QA state, and alpha verification report.
- `demo_prompts.json`: prompt metadata for all requested demo categories.

Do not add procedural demos, chroma-key demos, or single-background-removal demos.

Accepted demos:

| Demo | Status | Profile | Selected Candidate |
| --- | --- | --- | --- |
| `photorealistic-product-cutouts` | `passed` | `strict` | `black-green` |
| `photorealistic-human-model-cutouts` | `passed-relaxed-visual-qa` | `soft-photoreal` | `black-white` |
| `hair-alpha-stress-test` | `passed-relaxed-visual-qa` | `soft-photoreal` | `black-green` |
| `web-animation-sprite-strip` | `passed-relaxed-visual-qa` | `soft-photoreal` | `black-white` |
| `game-asset-pack` | `passed-relaxed-visual-qa` | `game-sprite` | `black-white` |
| `game-avatar-sprite-sheet` | `passed-relaxed-visual-qa` | `game-sprite` | `black-white` |
| `dialogue-avatar-portrait-pack` | `passed-relaxed-visual-qa` | `game-sprite` | `black-white` |
| `game-vfx-frames` | `passed-relaxed-visual-qa` | `game-sprite` | `black-white` |

Generate demos with:

```bash
python3 scripts/add_demo_pair.py \
  --demo-id <demo-id> \
  --black <codex-generated-black.png> \
  --white <codex-generated-white.png> \
  --green <codex-generated-green.png> \
  --force
```

Use Codex imagegen for the black and white generations. Generate green only after black/white `negative_diff_ratio` fails threshold. The white and optional green images must use the black image file as explicit reference input and request the black file's actual pixel size.

The validator copies files into this folder only after the active quality profile passes and PNG/WebP alpha verification pass. Relaxed `soft-photoreal` and `game-sprite` outputs require a second run with `--visual-qa-pass --visual-qa-note "..."` after the staged output is inspected and accepted.
