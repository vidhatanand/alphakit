# Transparent Image Methods

## Best Method Ranking

1. Native transparent generation or edit, followed by alpha verification.
2. Aligned black/white background extraction.
3. Single solid background removal, only when accepted as approximate.

## Black/White Pair Formula

For the same foreground `F` and alpha `a` composited over black and white:

```text
black_rgb = a * F
white_rgb = a * F + (1 - a)
white_rgb - black_rgb = 1 - a
a = 1 - (white_rgb - black_rgb)
F = black_rgb / a
```

This works only when the black and white images are aligned and the foreground is identical.

## Failure Modes

- Two independent generations usually change pose, edge detail, shadows, or object placement.
- Compression, bloom, shadows, and non-solid backgrounds corrupt the formula.
- Single-background removal loses semitransparent edges and struggles with foreground colors close to the background.
- WebP can preserve alpha, but lossy WebP can damage edges. Prefer lossless WebP when WebP is required.
