# Generate Transparent Image Skill

Codex skill for creating, extracting, and verifying true transparent PNG/WebP assets.

It supports:

- verifying whether a PNG/WebP has a real alpha channel
- extracting alpha from aligned black-background and white-background image pairs
- approximate single-solid-background removal
- synthetic self-tests that compare method quality and reject misaligned pairs

## Install

Clone this repository directly into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
git clone git@github.com:vidhatanand/generate-transparent-image-skill.git \
  ~/.codex/skills/generate-transparent-image
```

Restart Codex after installing so the skill is discovered.

## Use

Invoke it by name:

```text
Use $generate-transparent-image to create a true transparent PNG from this image prompt.
```

For an existing image:

```text
Use $generate-transparent-image to remove the background from this image and verify the PNG has real transparency.
```

## Verify Transparency

```bash
python3 scripts/verify_alpha.py output.png
```

If your system Python does not have Pillow installed, use the bundled Codex runtime:

```bash
/Users/vid/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/verify_alpha.py output.png
```

## Best Extraction Method

The most reliable extraction method is an aligned black/white pair:

```bash
python3 scripts/alpha_from_black_white.py \
  --black subject-on-black.png \
  --white subject-on-white.png \
  --out subject-transparent.png
```

This only works when both source images have identical subject placement and foreground pixels. Two independent AI generations usually do not align and should be treated as unsafe unless artifacts are acceptable.

## Test

```bash
/Users/vid/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/self_test.py
```

Expected result includes:

- aligned black/white alpha extraction with very low error
- single-background removal with higher error
- misaligned black/white pair rejected
- PNG and WebP alpha verification passing

