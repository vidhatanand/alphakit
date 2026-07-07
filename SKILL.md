---
name: alphakit
description: Generate, export, convert, and verify standard or transparent image assets from prompts or existing images using Codex image generation plus deterministic alpha/output scripts. Use when Codex is asked for prompt-to-image generation, JPEG/PNG/WebP output, transparent backgrounds, alpha-channel cutouts, background removal, PNG/WebP transparency verification, or black/white background alpha extraction from aligned image pairs.
---

# Alphakit

## Format Gate

Before generating, editing, exporting, or converting any image, determine the requested output format.

- If the user explicitly asks for `png`, `jpeg`, `jpg`, or `webp`, use that format.
- If the user does not specify a format, ask one concise question: `Which output format do you need: PNG, JPEG, or WebP?`
- Do not proceed with image generation/export until the format is known.
- Treat `jpg` as `jpeg`.

## Codex Image Generation Integration

When the user asks Alphakit to create an image from a prompt, use Codex image generation as the generation step. Do not replace prompt-to-image work with procedural placeholder assets.

Use this sequence:

1. Generate the source image with Codex's built-in image generation tool.
2. Copy the generated source from Codex's generated-images directory into the project or requested output folder. Leave the original generated file in place.
3. For opaque output, export the source to the requested format with `scripts/export_image.py`.
4. For transparent output, generate the source on a perfectly flat chroma-key background, remove that background with `scripts/remove_solid_background.py`, then verify alpha with `scripts/verify_alpha.py`.
5. Export WebP from the verified transparent PNG when WebP alpha is requested.

For transparent prompt-to-image generation, prompt Codex image generation with a removable key background:

```text
Create the requested subject on a perfectly flat solid #00ff00 chroma-key background for background removal.
The background must be one uniform color with no shadows, gradients, texture, reflections, floor plane, or lighting variation.
Keep the subject fully separated from the background with crisp edges and generous padding.
Do not use #00ff00 anywhere in the subject.
No cast shadow, no contact shadow, no reflection, no watermark, no text unless explicitly requested, and no checkerboard.
```

Use `#ff00ff` instead of `#00ff00` when the subject is likely to contain important green areas. If the generated source background is not flat enough for reliable removal, report that exact issue and regenerate with a stricter flat-background prompt. Do not silently fall back to synthetic or procedural demo art.

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
   - Generate the image with Codex image generation, then export/convert with `scripts/export_image.py` when the requested format differs from the generated file.
   - Use JPEG for opaque photographic images, PNG for lossless/general assets, and WebP when the user requests compact web delivery.

```bash
python3 scripts/export_image.py \
  --input generated.png \
  --format jpeg \
  --out final.jpg \
  --background "#ffffff"
```

2. **Best Codex transparent workflow: chroma-key source plus verified alpha**
   - Generate an isolated subject on a perfectly flat chroma-key background using Codex image generation.
   - Remove the background with `scripts/remove_solid_background.py`.
   - Verify with `verify_alpha.py`.
   - If alpha is missing, all opaque, or visibly contaminated by the key color, report that exact problem and regenerate or adjust the removal settings.

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
   - Use when Codex image generation produces one flat-key source image or when the user has one image and explicitly accepts lower accuracy.
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
- that Codex image generation is the source image generator

For transparent prompt-to-asset work, request:

- isolated subject only
- no checkerboard
- no background objects
- a perfectly flat chroma-key background for Codex image generation
- no shadows unless shadows are part of the subject and acceptable in the alpha
- no key color inside the subject

For black/white extraction pairs, keep the prompt and composition fixed. The only intended difference between the two images should be the background color.

## Output Requirements

- Ask for PNG/JPEG/WebP when the user does not specify a format.
- Save PNG for transparent output unless the user requests WebP with alpha.
- Save JPEG only for opaque output; flatten alpha onto a background color first.
- Save WebP as lossless when preserving alpha, or quality-controlled lossy for standard opaque images when requested.
- Re-run `verify_alpha.py` after every conversion.
- If verification fails, say what failed: missing alpha channel, all-opaque alpha, or no transparent pixels.
- Keep generated source images and final alpha outputs separate so the workflow is auditable.

## Resources

- `scripts/verify_alpha.py`: verify alpha channel and transparency stats.
- `scripts/export_image.py`: export/convert standard or transparent PNG/JPEG/WebP outputs.
- `scripts/alpha_from_black_white.py`: extract alpha from aligned black/white composites.
- `scripts/remove_solid_background.py`: lower-confidence single solid background removal.
- `scripts/self_test.py`: synthetic test comparing methods and misalignment sensitivity.
- `references/methods.md`: method details and failure modes.
