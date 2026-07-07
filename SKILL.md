---
name: alphakit
description: Generate, export, convert, and verify standard or transparent image assets from prompts or existing images using Codex image generation plus black/white pair alpha extraction with a controlled green-screen third-background fallback. Use when Codex is asked for prompt-to-image generation, JPEG/PNG/WebP output, transparent backgrounds, alpha-channel cutouts, PNG/WebP transparency verification, black/white background alpha extraction, or green-screen fallback extraction from aligned background pairs.
---

# Alphakit

## Format Defaults

Before generating, editing, exporting, or converting any image, determine the requested output format and transparency intent.

- If the user explicitly asks for `png`, `jpeg`, `jpg`, or `webp`, use that format.
- If the user does not specify a format, default to `png`.
- If the user does not specify whether the image should be opaque or transparent, default to a true transparent PNG with real alpha.
- If the user explicitly asks for a standard, opaque, or non-transparent image but does not specify a format, export an opaque PNG.
- Treat `jpg` as `jpeg`.

## Codex Image Generation Integration

When the user asks Alphakit to create an image from a prompt, use Codex image generation as the generation step. Do not replace prompt-to-image work with procedural placeholder assets.

If Codex image generation is not available in the current Codex session, warn the user that Codex imagegen is not installed or not exposed to this run, and stop before creating demos. Do not use the OpenAI API or require `OPENAI_API_KEY` unless the user explicitly opts into API-backed generation.

Use this sequence:

1. Generate the source image with Codex's built-in image generation tool.
2. Copy the generated source from Codex's generated-images directory into the project or requested output folder. Leave the original generated file in place.
3. For opaque output, export the source to the requested format with `scripts/export_image.py`.
4. For transparent output, use the black/white pair workflow below, then verify alpha with `scripts/verify_alpha.py`.
5. Export WebP from the verified transparent PNG when WebP alpha is requested.

For transparent prompt-to-image generation, use black/white pair extraction only:

1. Generate the subject on a pure black `#000000` background.
2. Read the first black image's actual pixel dimensions from disk.
3. Generate the second image with the first black image supplied as reference input, using image generation action `generate`, and request the actual first-image size.
4. Change only the background to pure white `#ffffff`.
5. Keep the subject geometry, pose, scale, lighting, pixels, edges, and placement unchanged.
6. Run `scripts/add_demo_pair.py` or `scripts/alpha_from_black_white.py` on the aligned black and white images.
7. If extraction fails because `negative_diff_ratio` exceeds threshold, generate the green third image below, then rerun `scripts/add_demo_pair.py --green`.
8. Verify the output with `scripts/verify_alpha.py`.
9. Use `--quality-profile soft-photoreal` only when the user accepts relaxed handling for hair, shadows, glass, smoke, or other soft photoreal edges. Relaxed outputs must stop for visual QA and must not be copied into examples unless rerun with `--visual-qa-pass`.

First image prompt:

```text
Create the requested subject on a perfectly flat solid #000000 background for black/white alpha extraction.
The background must be one uniform black color with no shadows, gradients, texture, reflections, floor plane, or lighting variation.
Keep the subject fully separated from the background with crisp edges and generous padding.
No cast shadow, no contact shadow, no reflection, no watermark, no text unless explicitly requested, and no checkerboard.
```

Second image reference-generation prompt:

```text
Use this exact image as the reference target. Generate a second image that changes only the background from pure black to pure white.
Do not change the subject, pose, scale, crop, camera, lighting, colors, edges, shadows, or pixel placement.
The output must be identical to the input except the background color is #ffffff.
```

Do not create the white image as an independent text-only generation. If reference generation cannot preserve alignment, report that the black/white pair is invalid and stop. Do not switch to image edit, standalone chroma-key removal, or procedural stand-ins.

Always set the second/reference generation size from the actual black image file, not from the requested manifest size. If the API cannot produce the white image at the actual black image dimensions, report that exact size mismatch and reject the pair.

Third image green reference-generation prompt, only after `negative_diff_ratio` fails threshold:

```text
Use this exact black-background image as the reference target. Generate a third image that changes only the background from pure black to pure green #00ff00.
Do not change the subject, pose, scale, crop, camera, lighting, colors, edges, shadows, or pixel placement.
The output must be identical to the input except the background color is #00ff00.
```

Generate the green third image only after black/white extraction reports `negative_diff_ratio` above the configured threshold. Use `scripts/add_demo_pair.py --green green.png`; it evaluates black-white, black-green, and green-white candidates, then selects the passing candidate with the lowest `negative_diff_ratio`.

## Quality Profiles

Use the default `strict` profile unless the user explicitly asks to relax artifact risk.

- `strict`: default demo gate. Uses `negative_diff_ratio <= 0.03`, tight channel-spread limits, and snaps very low alpha to transparent in the saved output.
- `soft-photoreal`: opt-in relaxed gate for hair, soft shadows, glass, smoke, and photoreal edge cases. Uses looser thresholds and requires `--visual-qa-pass` before `scripts/add_demo_pair.py` copies outputs into `examples/`.

For relaxed demos, first run without `--visual-qa-pass`, inspect the staged PNG/WebP paths in the report, then rerun with `--visual-qa-pass --visual-qa-note "..."`
only if the user accepts the visible quality tradeoff. If the profile thresholds still fail, do not copy the demo and do not use another fallback unless the user decides to.

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
   - Use PNG when the user does not specify a format.
   - Generate the image with Codex image generation, then export/convert with `scripts/export_image.py` when the requested format differs from the generated file.
   - Use JPEG for opaque photographic images, PNG for lossless/general assets, and WebP when the user requests compact web delivery.

```bash
python3 scripts/export_image.py \
  --input generated.png \
  --format jpeg \
  --out final.jpg \
  --background "#ffffff"
```

2. **Transparent extraction method: aligned solid-background pairs**
   - Use when you have the same foreground composited over pure black and pure white backgrounds with identical geometry.
   - Do not use two independent generations; they usually will not align.
   - Create the first image on black, read its actual dimensions, then generate the white-background image with the black image as reference input and the actual black-image size while preserving subject placement.
   - If black/white fails only because `negative_diff_ratio` exceeds threshold, generate a green-background third image with the black image as reference input and rerun `add_demo_pair.py --green`.
   - Use the passing candidate with the lowest `negative_diff_ratio`.
   - Use `--quality-profile soft-photoreal` only as an explicit, visual-QA-gated relaxation.
   - Extract with:

```bash
python3 scripts/alpha_from_black_white.py \
  --black subject_on_black.png \
  --white subject_on_white.png \
  --out subject-transparent.png
```

## Prompting Guidance

For standard prompt-to-asset work, include:

- requested format, defaulting to PNG when unspecified
- intended aspect ratio or dimensions when known
- whether the image must be opaque or transparent
- if JPEG is requested, no transparency because JPEG cannot store alpha
- that Codex image generation is the source image generator

For transparent prompt-to-asset work, request:

- isolated subject only
- no checkerboard
- no background objects
- a pure black first image and pure white reference-generated second image
- a pure green third image only after black/white `negative_diff_ratio` fails threshold
- identical subject geometry, pose, scale, crop, lighting, pixels, edges, and placement across the pair
- no shadows unless shadows are part of the subject and must be preserved in the alpha

For black/white extraction pairs, the only intended difference between the two images must be the background color.
For green fallback, do not use green as chroma-key removal; use it only as an additional solid-background extraction candidate with black and white.

## Output Requirements

- Default to true transparent PNG when the user does not specify a format or opacity requirement.
- Save PNG for transparent output unless the user explicitly requests WebP with alpha.
- Save JPEG only for opaque output; flatten alpha onto a background color first.
- Save WebP as lossless when preserving alpha, or quality-controlled lossy for standard opaque images when requested.
- Re-run `verify_alpha.py` after every conversion.
- If verification fails, say what failed: missing alpha channel, all-opaque alpha, or no transparent pixels.
- The default `negative_diff_ratio` threshold is `0.03`; do not use `soft-photoreal` unless the user explicitly accepts artifacts and visual QA.
- Keep generated source images and final alpha outputs separate so the workflow is auditable.

## Resources

- `scripts/verify_alpha.py`: verify alpha channel and transparency stats.
- `scripts/export_image.py`: export/convert standard or transparent PNG/JPEG/WebP outputs.
- `scripts/quality_profiles.py`: central strict and `soft-photoreal` thresholds plus low-alpha snap settings.
- `scripts/alpha_from_background_pair.py`: extract alpha from two aligned composites over known solid backgrounds, including black/green and green/white.
- `scripts/alpha_from_black_white.py`: extract alpha from aligned black/white composites.
- `scripts/responses_reference_generate.py`: generate with a reference image through Responses image_generation.
- `scripts/generate_demo_pairs.py`: generate demo candidates with explicit black-image reference targets, size the white generation from the actual black image, and add only profile-passing outputs.
- `scripts/add_demo_pair.py`: validate and copy Codex-imagegen black/white outputs, with optional green fallback after negative-diff failure, into `examples/` only when the active profile passes and relaxed profiles have visual QA approval.
- `scripts/self_test.py`: synthetic test for black/white extraction, verification, export, and misalignment rejection.
- `references/methods.md`: method details and failure modes.
