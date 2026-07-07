#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quality_profiles import (
    passes_thresholds,
    profile_names,
    profile_report,
    resolve_snap_alpha_below,
    resolve_thresholds,
)


def require_deps():
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pillow and NumPy are required. Use the bundled Codex Python runtime or install "
            "Pillow and NumPy for this interpreter."
        ) from exc
    return np, Image, ImageFilter


def parse_color(value: str):
    value = value.strip().lower()
    if value.startswith("#") and len(value) == 7:
        return tuple(int(value[index : index + 2], 16) / 255.0 for index in (1, 3, 5))
    parts = [part.strip() for part in value.split(",")]
    if len(parts) == 3:
        return tuple(max(0, min(255, int(part))) / 255.0 for part in parts)
    raise argparse.ArgumentTypeError("Use #RRGGBB or r,g,b.")


def load_rgb(path: Path):
    np, Image, _ImageFilter = require_deps()
    image = Image.open(path).convert("RGB")
    return image, np.asarray(image, dtype=np.float32) / 255.0


def extract_rgba_arrays(first_rgb, second_rgb, first_bg, second_bg):
    np, _Image, _ImageFilter = require_deps()
    first_bg = np.asarray(first_bg, dtype=np.float32)
    second_bg = np.asarray(second_bg, dtype=np.float32)
    denom = second_bg - first_bg
    used_channels = np.abs(denom) > (1.0 / 255.0)
    if not bool(np.any(used_channels)):
        raise SystemExit("Background colors must differ in at least one RGB channel.")

    diff = second_rgb - first_rgb
    normalized_diff = diff[..., used_channels] / denom[used_channels]
    alpha_channels = 1.0 - normalized_diff
    alpha = np.clip(np.median(alpha_channels, axis=2), 0.0, 1.0)

    rgba_rgb = np.zeros_like(first_rgb)
    mask = alpha > 1.0 / 255.0
    rgba_rgb[mask] = (first_rgb[mask] - (1.0 - alpha[mask, None]) * first_bg) / alpha[mask, None]
    rgba_rgb = np.clip(rgba_rgb, 0.0, 1.0)

    channel_spread = np.std(alpha_channels, axis=2) if alpha_channels.shape[2] > 1 else np.zeros_like(alpha)
    return rgba_rgb, alpha, channel_spread, normalized_diff, used_channels


def save_rgba(rgb, alpha, out_path: Path, feather: float = 0.0, snap_alpha_below: int = 0):
    np, Image, ImageFilter = require_deps()
    rgb = rgb.copy()
    alpha = alpha.copy()
    if snap_alpha_below > 0:
        snap_limit = max(0, min(255, snap_alpha_below)) / 255.0
        snap_mask = alpha <= snap_limit
        alpha[snap_mask] = 0.0
        rgb[snap_mask] = 0.0
    rgba = np.dstack([rgb, alpha])
    image = Image.fromarray(np.clip(rgba * 255.0 + 0.5, 0, 255).astype("uint8"), "RGBA")

    if feather > 0:
        alpha_channel = image.getchannel("A").filter(ImageFilter.GaussianBlur(feather))
        image.putalpha(alpha_channel)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = out_path.suffix.lower()
    if suffix == ".webp":
        image.save(out_path, format="WEBP", lossless=True, quality=100, method=6)
    else:
        image.save(out_path, format="PNG")


def summarize(alpha, spread, normalized_diff, used_channels):
    np, _Image, _ImageFilter = require_deps()
    negative_diff = normalized_diff < -(1.0 / 255.0)
    too_high_diff = normalized_diff > (1.0 + 1.0 / 255.0)
    return {
        "alpha_min": float(alpha.min()),
        "alpha_max": float(alpha.max()),
        "transparent_pixels": int((alpha < 1.0 / 255.0).sum()),
        "semi_transparent_pixels": int(((alpha >= 1.0 / 255.0) & (alpha < 254.0 / 255.0)).sum()),
        "opaque_pixels": int((alpha >= 254.0 / 255.0).sum()),
        "channel_spread_mean": float(spread.mean()),
        "channel_spread_p95": float(np.quantile(spread, 0.95)),
        "channel_spread_p99": float(np.quantile(spread, 0.99)),
        "channel_spread_max": float(spread.max()),
        "negative_diff_ratio": float(np.any(negative_diff, axis=2).mean()),
        "too_high_diff_ratio": float(np.any(too_high_diff, axis=2).mean()),
        "alpha_channel_count": int(np.asarray(used_channels).sum()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract true alpha from two aligned composites over known solid backgrounds."
    )
    parser.add_argument("--first", required=True, type=Path)
    parser.add_argument("--second", required=True, type=Path)
    parser.add_argument("--first-bg", required=True, type=parse_color)
    parser.add_argument("--second-bg", required=True, type=parse_color)
    parser.add_argument("--candidate-name", default="background-pair")
    parser.add_argument("--out", required=True, type=Path, help="Output PNG or WebP with alpha.")
    parser.add_argument("--feather", type=float, default=0.0, help="Optional alpha blur radius.")
    parser.add_argument("--quality-profile", choices=profile_names(), default="strict")
    parser.add_argument("--max-spread-p95", type=float)
    parser.add_argument("--max-spread-p99", type=float)
    parser.add_argument("--max-spread-max", type=float)
    parser.add_argument("--max-negative-ratio", type=float)
    parser.add_argument("--max-too-high-ratio", type=float)
    parser.add_argument(
        "--snap-alpha-below",
        type=int,
        help="Set pixels with alpha at or below this 0-255 value to fully transparent.",
    )
    parser.add_argument("--no-strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    thresholds = resolve_thresholds(
        profile_name=args.quality_profile,
        max_spread_p95=args.max_spread_p95,
        max_spread_p99=args.max_spread_p99,
        max_spread_max=args.max_spread_max,
        max_negative_ratio=args.max_negative_ratio,
        max_too_high_ratio=args.max_too_high_ratio,
    )
    snap_alpha_below = resolve_snap_alpha_below(args.quality_profile, args.snap_alpha_below)

    first_image, first_rgb = load_rgb(args.first)
    second_image, second_rgb = load_rgb(args.second)

    if first_image.size != second_image.size:
        raise SystemExit(
            f"Input dimensions differ: first={first_image.size}, second={second_image.size}. "
            "Aligned extraction requires identical dimensions."
        )

    rgb, alpha, spread, normalized_diff, used_channels = extract_rgba_arrays(
        first_rgb, second_rgb, args.first_bg, args.second_bg
    )
    report = summarize(alpha, spread, normalized_diff, used_channels)
    profile_pass = passes_thresholds(report, thresholds)
    report.update(
        {
            "candidate_name": args.candidate_name,
            "first": str(args.first),
            "second": str(args.second),
            "first_bg": args.first_bg,
            "second_bg": args.second_bg,
            "out": str(args.out),
            "width": first_image.width,
            "height": first_image.height,
            "quality_profile": args.quality_profile,
            "quality_profile_report": profile_report(args.quality_profile, thresholds),
            "profile_pass": profile_pass,
            "strict_pass": profile_pass,
            "max_negative_ratio": thresholds["max_negative_ratio"],
            "max_spread_p95": thresholds["max_spread_p95"],
            "max_spread_p99": thresholds["max_spread_p99"],
            "max_spread_max": thresholds["max_spread_max"],
            "max_too_high_ratio": thresholds["max_too_high_ratio"],
            "snap_alpha_below": snap_alpha_below,
        }
    )

    if not report["profile_pass"] and not args.no_strict:
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        raise SystemExit(
            "Background pair appears inconsistent or misaligned "
            f"(candidate={args.candidate_name}, "
            f"profile={args.quality_profile}, "
            f"p99={report['channel_spread_p99']:.4f}, "
            f"max={report['channel_spread_max']:.4f}, "
            f"negative_diff_ratio={report['negative_diff_ratio']:.4f}). "
            "Use --no-strict only if you accept artifacts."
        )

    save_rgba(rgb, alpha, args.out, feather=args.feather, snap_alpha_below=snap_alpha_below)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")

    return 0 if report["profile_pass"] else 4


if __name__ == "__main__":
    sys.exit(main())
