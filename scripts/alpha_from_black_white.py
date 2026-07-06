#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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


def load_rgb(path: Path):
    np, Image, _ImageFilter = require_deps()
    image = Image.open(path).convert("RGB")
    return image, np.asarray(image, dtype=np.float32) / 255.0


def extract_rgba_arrays(black_rgb, white_rgb):
    np, _Image, _ImageFilter = require_deps()
    diff = white_rgb - black_rgb
    alpha_channels = 1.0 - diff
    alpha = np.clip(np.median(alpha_channels, axis=2), 0.0, 1.0)

    rgba_rgb = np.zeros_like(black_rgb)
    mask = alpha > 1.0 / 255.0
    rgba_rgb[mask] = black_rgb[mask] / alpha[mask, None]
    rgba_rgb = np.clip(rgba_rgb, 0.0, 1.0)

    channel_spread = np.std(alpha_channels, axis=2)
    return rgba_rgb, alpha, channel_spread


def save_rgba(rgb, alpha, out_path: Path, feather: float = 0.0):
    np, Image, ImageFilter = require_deps()
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


def summarize(alpha, spread, diff):
    np, _Image, _ImageFilter = require_deps()
    negative_diff = diff < -(1.0 / 255.0)
    too_high_diff = diff > (1.0 + 1.0 / 255.0)
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
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract true alpha from aligned pure-black and pure-white composites."
    )
    parser.add_argument("--black", required=True, type=Path, help="Image composited over #000000.")
    parser.add_argument("--white", required=True, type=Path, help="Image composited over #ffffff.")
    parser.add_argument("--out", required=True, type=Path, help="Output PNG or WebP with alpha.")
    parser.add_argument("--feather", type=float, default=0.0, help="Optional alpha blur radius.")
    parser.add_argument(
        "--max-spread-p95",
        type=float,
        default=0.12,
        help="Fail if p95 channel inconsistency exceeds this value.",
    )
    parser.add_argument(
        "--max-spread-p99",
        type=float,
        default=0.015,
        help="Fail if p99 channel inconsistency exceeds this value.",
    )
    parser.add_argument(
        "--max-spread-max",
        type=float,
        default=0.12,
        help="Fail if maximum channel inconsistency exceeds this value.",
    )
    parser.add_argument(
        "--max-negative-ratio",
        type=float,
        default=0.001,
        help="Fail if this ratio of pixels has white darker than black.",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="Write output even when the pair appears inconsistent or misaligned.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    args = parser.parse_args()

    black_image, black_rgb = load_rgb(args.black)
    white_image, white_rgb = load_rgb(args.white)

    if black_image.size != white_image.size:
        raise SystemExit(
            f"Input dimensions differ: black={black_image.size}, white={white_image.size}. "
            "Aligned extraction requires identical dimensions."
        )

    diff = white_rgb - black_rgb
    rgb, alpha, spread = extract_rgba_arrays(black_rgb, white_rgb)
    report = summarize(alpha, spread, diff)
    strict_pass = (
        report["channel_spread_p95"] <= args.max_spread_p95
        and report["channel_spread_p99"] <= args.max_spread_p99
        and report["channel_spread_max"] <= args.max_spread_max
        and report["negative_diff_ratio"] <= args.max_negative_ratio
        and report["too_high_diff_ratio"] == 0
    )
    report.update(
        {
            "black": str(args.black),
            "white": str(args.white),
            "out": str(args.out),
            "width": black_image.width,
            "height": black_image.height,
            "strict_pass": strict_pass,
        }
    )

    if not report["strict_pass"] and not args.no_strict:
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        raise SystemExit(
            "Black/white pair appears inconsistent or misaligned "
            f"(p99={report['channel_spread_p99']:.4f}, "
            f"max={report['channel_spread_max']:.4f}, "
            f"negative_diff_ratio={report['negative_diff_ratio']:.4f}). "
            "Use --no-strict only if you accept artifacts."
        )

    save_rgba(rgb, alpha, args.out, feather=args.feather)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")

    return 0 if report["strict_pass"] else 4


if __name__ == "__main__":
    sys.exit(main())
