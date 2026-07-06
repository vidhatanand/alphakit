---
name: generate-transparent-image
description: Generate, export, convert, and verify standard or transparent image assets from prompts or existing images. Use when Codex is asked for image generation, JPEG/PNG/WebP output, transparent backgrounds, alpha-channel cutouts, background removal, PNG/WebP transparency verification, or black/white background alpha extraction from aligned image pairs.
---

# Generate Transparent Image

## Format Gate

Before generating, editing, exporting, or converting any image, determine the requested output format.

- If the user explicitly asks for `png`, `jpeg`, `jpg`, or `webp`, use that format.
- If the user does not specify a format, ask one concise question: `Which output format do you need: PNG, JPEG, or WebP?`
- Do not proceed with image generation/export until the format is known.
- Treat `jpg` as `jpeg`.

## Core Rule

For transparent output, always verify the output file has a real alpha channel. A checkerboard preview is not proof of transparency.

Run:

```bash
python3 scripts/verify_alpha.py output.png
```

Use the bundled Codex Python runtime if the active `python3` does not have Pillow:

```bash
/Users/vid/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/verify_alpha.py output.png
```

## Method Choice

1. **Standard image generation**
   - Use when the user wants a normal non-transparent image.
   - Ask for format first if missing.
   - Generate the image, then export/convert with `scripts/export_image.py` when the requested format differs from the generated file.
   - Use JPEG for opaque photographic images, PNG for lossless/general assets, and WebP when the user requests compact web delivery.

```bash
python3 scripts/export_image.py \
  --input generated.png \
  --format jpeg \
  --out final.jpg \
  --background "#ffffff"
```

2. **Best transparent first attempt: true-alpha generation or edit**
   - Ask image generation for an isolated subject with transparent background.
   - Verify with `verify_alpha.py`.
   - If alpha is missing or all opaque, report that exact problem.

3. **Best transparent extraction method: aligned black/white pair**
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

4. **Limited transparent method: single solid background removal**
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

For standard prompt-to-asset work, include:

- requested format
- intended aspect ratio or dimensions when known
- whether the image must be opaque or transparent
- if JPEG is requested, no transparency because JPEG cannot store alpha

For transparent prompt-to-asset work, request:

- isolated subject only
- no checkerboard
- no background objects
- pure transparent background if the generator supports it
- if extracting later, pure black or pure white background with no shadows unless shadows are part of the subject

For black/white extraction pairs, keep the prompt and composition fixed. The only intended difference between the two images should be the background color.

## Output Requirements

- Ask for PNG/JPEG/WebP when the user does not specify a format.
- Save PNG for transparent output unless the user requests WebP with alpha.
- Save JPEG only for opaque output; flatten alpha onto a background color first.
- Save WebP as lossless when preserving alpha, or quality-controlled lossy for standard opaque images when requested.
- Re-run `verify_alpha.py` after every conversion.
- If verification fails, say what failed: missing alpha channel, all-opaque alpha, or no transparent pixels.

## Resources

- `scripts/verify_alpha.py`: verify alpha channel and transparency stats.
- `scripts/export_image.py`: export/convert standard or transparent PNG/JPEG/WebP outputs.
- `scripts/alpha_from_black_white.py`: extract alpha from aligned black/white composites.
- `scripts/remove_solid_background.py`: lower-confidence single solid background removal.
- `scripts/self_test.py`: synthetic test comparing methods and misalignment sensitivity.
- `references/methods.md`: method details and failure modes.
