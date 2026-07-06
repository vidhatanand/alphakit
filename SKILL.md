---
name: generate-transparent-image
description: Generate and verify true transparent PNG/WebP image assets from prompts or existing images. Use when Codex is asked for transparent backgrounds, alpha-channel cutouts, background removal, PNG/WebP transparency verification, or black/white background alpha extraction from aligned image pairs.
---

# Generate Transparent Image

## Core Rule

Always verify the output file has a real alpha channel. A checkerboard preview is not proof of transparency.

Run:

```bash
python3 scripts/verify_alpha.py output.png
```

Use the bundled Codex Python runtime if the active `python3` does not have Pillow:

```bash
/Users/vid/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/verify_alpha.py output.png
```

## Method Choice

1. **Best first attempt: true-alpha generation or edit**
   - Ask image generation for an isolated subject with transparent background.
   - Verify with `verify_alpha.py`.
   - If alpha is missing or all opaque, report that exact problem.

2. **Best extraction method: aligned black/white pair**
   - Use when you have the same foreground composited over pure black and pure white backgrounds with identical geometry.
   - Do not use two independent generations unless the user explicitly accepts likely artifacts; they usually will not align.
   - Prefer creating one image, then editing only the background to black/white while preserving subject placement.
   - Extract with:

```bash
python3 scripts/alpha_from_black_white.py \
  --black subject_on_black.png \
  --white subject_on_white.png \
  --out subject-transparent.png
```

3. **Limited method: single solid background removal**
   - Use only when the user has one image and explicitly accepts lower accuracy.
   - Works best for hard-edged subjects on pure black, white, or chroma backgrounds.
   - It cannot recover true semitransparent edges as reliably as an aligned black/white pair.

```bash
python3 scripts/remove_solid_background.py \
  --input subject_on_black.png \
  --bg "#000000" \
  --out subject-transparent.png
```

## Prompting Guidance

For prompt-to-asset work, request:

- isolated subject only
- no checkerboard
- no background objects
- pure transparent background if the generator supports it
- if extracting later, pure black or pure white background with no shadows unless shadows are part of the subject

For black/white extraction pairs, keep the prompt and composition fixed. The only intended difference between the two images should be the background color.

## Output Requirements

- Save PNG for maximum compatibility.
- Save WebP only when requested; use lossless WebP with alpha.
- Re-run `verify_alpha.py` after every conversion.
- If verification fails, say what failed: missing alpha channel, all-opaque alpha, or no transparent pixels.

## Resources

- `scripts/verify_alpha.py`: verify alpha channel and transparency stats.
- `scripts/alpha_from_black_white.py`: extract alpha from aligned black/white composites.
- `scripts/remove_solid_background.py`: lower-confidence single solid background removal.
- `scripts/self_test.py`: synthetic test comparing methods and misalignment sensitivity.
- `references/methods.md`: method details and failure modes.
