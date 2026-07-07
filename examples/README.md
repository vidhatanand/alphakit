# Alphakit Examples

This folder contains transparent sample assets generated for the Alphakit README.

- `transparent/*.png`: true-alpha PNG examples.
- `transparent/*.webp`: lossless WebP alpha exports of the same examples.
- `prompts.json`: prompt, category, and output path metadata for each example.

The main README includes advanced prompt recipes for photorealistic cutouts, web animation sprites, game asset sheets, and VFX frames.

Regenerate them with:

```bash
/Users/vid/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  scripts/build_examples.py
```

Verify them with:

```bash
for image in examples/transparent/*.{png,webp}; do
  /Users/vid/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
    scripts/verify_alpha.py "$image" >/dev/null
done
```
