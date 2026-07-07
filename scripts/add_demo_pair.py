#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from quality_profiles import get_profile, profile_names, profile_report, resolve_thresholds


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
DEFAULT_EXAMPLES_DIR = REPO_DIR / "examples"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_DIR, text=True, capture_output=True, check=False)


def parse_json(stdout: str) -> dict[str, object]:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw_stdout": stdout}


def require_same_size(black: Path, white: Path) -> tuple[int, int]:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pillow is required. Use the bundled Codex Python runtime or install Pillow."
        ) from exc

    with Image.open(black) as black_image, Image.open(white) as white_image:
        if black_image.size != white_image.size:
            raise SystemExit(
                f"Input dimensions differ: black={black_image.size}, white={white_image.size}. "
                "Codex imagegen must generate the white reference at the actual black image size."
            )
        return black_image.size


def require_matching_size(reference: Path, candidate: Path, *, reference_label: str, candidate_label: str) -> None:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pillow is required. Use the bundled Codex Python runtime or install Pillow."
        ) from exc

    with Image.open(reference) as reference_image, Image.open(candidate) as candidate_image:
        if reference_image.size != candidate_image.size:
            raise SystemExit(
                f"Input dimensions differ: {reference_label}={reference_image.size}, "
                f"{candidate_label}={candidate_image.size}. All background candidates must use "
                "the actual black image size."
            )


def final_paths(examples_dir: Path, demo_id: str) -> dict[str, Path]:
    return {
        "black": examples_dir / "pairs" / f"{demo_id}-black.png",
        "white": examples_dir / "pairs" / f"{demo_id}-white.png",
        "green": examples_dir / "pairs" / f"{demo_id}-green.png",
        "png": examples_dir / "transparent" / f"{demo_id}.png",
        "webp": examples_dir / "transparent" / f"{demo_id}.webp",
        "report": examples_dir / "reports" / f"{demo_id}.json",
    }


def ensure_no_overwrite(paths: dict[str, Path], force: bool) -> None:
    if force:
        return
    existing = [str(path) for path in paths.values() if path.exists()]
    if existing:
        raise SystemExit(
            "Refusing to overwrite existing demo outputs without --force:\n"
            + "\n".join(existing)
        )


def candidate_command(
    *,
    name: str,
    first: Path,
    second: Path,
    first_bg: str,
    second_bg: str,
    out: Path,
    quality_profile: str,
    thresholds: dict[str, float],
) -> list[str]:
    return [
        sys.executable,
        str(SCRIPT_DIR / "alpha_from_background_pair.py"),
        "--candidate-name",
        name,
        "--first",
        str(first),
        "--second",
        str(second),
        "--first-bg",
        first_bg,
        "--second-bg",
        second_bg,
        "--out",
        str(out),
        "--quality-profile",
        quality_profile,
        "--max-spread-p95",
        str(thresholds["max_spread_p95"]),
        "--max-spread-p99",
        str(thresholds["max_spread_p99"]),
        "--max-spread-max",
        str(thresholds["max_spread_max"]),
        "--max-negative-ratio",
        str(thresholds["max_negative_ratio"]),
        "--max-too-high-ratio",
        str(thresholds["max_too_high_ratio"]),
        "--json",
    ]


def candidate_report(
    *,
    name: str,
    command: list[str],
    out: Path,
) -> dict[str, object]:
    result = run(command)
    parsed = parse_json(result.stdout)
    return {
        "name": name,
        "out": str(out),
        "returncode": result.returncode,
        "report": parsed,
        "stderr": result.stderr,
        "negative_diff_ratio": float(parsed.get("negative_diff_ratio", 1.0)) if isinstance(parsed, dict) else 1.0,
        "profile_pass": bool(parsed.get("profile_pass", parsed.get("strict_pass"))) if isinstance(parsed, dict) else False,
        "strict_pass": bool(parsed.get("strict_pass")) if isinstance(parsed, dict) else False,
    }


def select_candidate(candidates: list[dict[str, object]]) -> dict[str, object] | None:
    passing = [candidate for candidate in candidates if candidate.get("profile_pass")]
    if not passing:
        return None
    return min(passing, key=lambda candidate: float(candidate.get("negative_diff_ratio", 1.0)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strictly validate and add a Codex-imagegen black/white demo pair."
    )
    parser.add_argument("--demo-id", required=True)
    parser.add_argument("--black", required=True, type=Path)
    parser.add_argument("--white", required=True, type=Path)
    parser.add_argument(
        "--green",
        type=Path,
        help="Optional green-screen image generated only after black/white negative_diff_ratio fails.",
    )
    parser.add_argument("--examples-dir", type=Path, default=DEFAULT_EXAMPLES_DIR)
    parser.add_argument("--quality-profile", choices=profile_names(), default="strict")
    parser.add_argument("--max-spread-p95", type=float)
    parser.add_argument("--max-spread-p99", type=float)
    parser.add_argument("--max-spread-max", type=float)
    parser.add_argument("--max-negative-ratio", type=float)
    parser.add_argument("--max-too-high-ratio", type=float)
    parser.add_argument(
        "--visual-qa-pass",
        action="store_true",
        help="Required before copying demos that pass only under a relaxed profile.",
    )
    parser.add_argument("--visual-qa-note", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    thresholds = resolve_thresholds(
        profile_name=args.quality_profile,
        max_spread_p95=args.max_spread_p95,
        max_spread_p99=args.max_spread_p99,
        max_spread_max=args.max_spread_max,
        max_negative_ratio=args.max_negative_ratio,
        max_too_high_ratio=args.max_too_high_ratio,
    )
    profile = get_profile(args.quality_profile)

    args.black = args.black.resolve()
    args.white = args.white.resolve()
    args.green = args.green.resolve() if args.green else None
    args.examples_dir = args.examples_dir.resolve()
    if not args.black.exists():
        raise SystemExit(f"Black image not found: {args.black}")
    if not args.white.exists():
        raise SystemExit(f"White image not found: {args.white}")
    if args.green and not args.green.exists():
        raise SystemExit(f"Green image not found: {args.green}")

    width, height = require_same_size(args.black, args.white)
    if args.green:
        require_matching_size(args.black, args.green, reference_label="black", candidate_label="green")
    paths = final_paths(args.examples_dir, args.demo_id)
    ensure_no_overwrite(paths, args.force)

    stage = Path("/tmp") / f"alphakit-add-demo-{args.demo_id}"
    stage.mkdir(parents=True, exist_ok=True)
    stage_png = stage / f"{args.demo_id}.png"
    stage_webp = stage / f"{args.demo_id}.webp"

    bw_out = stage / f"{args.demo_id}-black-white.png"
    bw_command = candidate_command(
        name="black-white",
        first=args.black,
        second=args.white,
        first_bg="#000000",
        second_bg="#ffffff",
        out=bw_out,
        quality_profile=args.quality_profile,
        thresholds=thresholds,
    )
    bw_candidate = candidate_report(name="black-white", command=bw_command, out=bw_out)
    bw_report = bw_candidate["report"] if isinstance(bw_candidate["report"], dict) else {}
    report: dict[str, object] = {
        "demo_id": args.demo_id,
        "black": str(args.black),
        "white": str(args.white),
        "green": str(args.green) if args.green else None,
        "width": width,
        "height": height,
        "quality_profile": args.quality_profile,
        "quality_profile_report": profile_report(args.quality_profile, thresholds),
        "visual_qa_required": profile.requires_visual_qa,
        "visual_qa_passed": args.visual_qa_pass,
        "visual_qa_note": args.visual_qa_note,
        "max_negative_ratio": thresholds["max_negative_ratio"],
        "commands": {"black_white": bw_command},
        "candidates": [bw_candidate],
        "status": "started",
    }

    selected = select_candidate([bw_candidate])
    negative_failed = float(bw_report.get("negative_diff_ratio", 1.0)) > thresholds["max_negative_ratio"]
    if selected is None and negative_failed:
        if not args.green:
            report["status"] = "failed-negative-diff-needs-green"
            report["green_required"] = (
                "Generate a green-screen third image only because black/white "
                "negative_diff_ratio exceeded the threshold, then rerun with --green."
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return int(bw_candidate["returncode"]) if int(bw_candidate["returncode"]) else 1

        green_candidates = [
            (
                "black-green",
                args.black,
                args.green,
                "#000000",
                "#00ff00",
                stage / f"{args.demo_id}-black-green.png",
            ),
            (
                "green-white",
                args.green,
                args.white,
                "#00ff00",
                "#ffffff",
                stage / f"{args.demo_id}-green-white.png",
            ),
        ]
        for name, first, second, first_bg, second_bg, out in green_candidates:
            command = candidate_command(
                name=name,
                first=first,
                second=second,
                first_bg=first_bg,
                second_bg=second_bg,
                out=out,
                quality_profile=args.quality_profile,
                thresholds=thresholds,
            )
            report["commands"][name.replace("-", "_")] = command  # type: ignore[index]
            report["candidates"].append(candidate_report(name=name, command=command, out=out))  # type: ignore[union-attr]
        selected = select_candidate(report["candidates"])  # type: ignore[arg-type]

    if selected is None:
        report["status"] = "failed-profile-extraction"
        report["selection_rule"] = "No candidate passed the active quality profile thresholds."
        print(json.dumps(report, indent=2, sort_keys=True))
        return int(bw_candidate["returncode"]) if int(bw_candidate["returncode"]) else 1

    selected_out = Path(str(selected["out"]))
    shutil.copy2(selected_out, stage_png)
    report["selected_candidate"] = selected["name"]
    report["selection_rule"] = "Selected the passing candidate with the lowest negative_diff_ratio."
    report["stage_png"] = str(stage_png)
    report["stage_webp"] = str(stage_webp)

    verify_png_command = [
        sys.executable,
        str(SCRIPT_DIR / "verify_alpha.py"),
        str(stage_png),
        "--json",
    ]
    verify_png_result = run(verify_png_command)
    report["commands"]["verify_png"] = verify_png_command  # type: ignore[index]
    report["verify_png"] = {
        "returncode": verify_png_result.returncode,
        "report": parse_json(verify_png_result.stdout),
        "stderr": verify_png_result.stderr,
    }
    if verify_png_result.returncode != 0:
        report["status"] = "failed-png-alpha-verification"
        print(json.dumps(report, indent=2, sort_keys=True))
        return verify_png_result.returncode

    export_webp_command = [
        sys.executable,
        str(SCRIPT_DIR / "export_image.py"),
        "--input",
        str(stage_png),
        "--format",
        "webp",
        "--out",
        str(stage_webp),
        "--preserve-alpha",
        "--lossless",
        "--json",
    ]
    export_webp_result = run(export_webp_command)
    report["commands"]["export_webp"] = export_webp_command  # type: ignore[index]
    report["export_webp"] = {
        "returncode": export_webp_result.returncode,
        "report": parse_json(export_webp_result.stdout),
        "stderr": export_webp_result.stderr,
    }
    if export_webp_result.returncode != 0:
        report["status"] = "failed-webp-export"
        print(json.dumps(report, indent=2, sort_keys=True))
        return export_webp_result.returncode

    verify_webp_command = [
        sys.executable,
        str(SCRIPT_DIR / "verify_alpha.py"),
        str(stage_webp),
        "--json",
    ]
    verify_webp_result = run(verify_webp_command)
    report["commands"]["verify_webp"] = verify_webp_command  # type: ignore[index]
    report["verify_webp"] = {
        "returncode": verify_webp_result.returncode,
        "report": parse_json(verify_webp_result.stdout),
        "stderr": verify_webp_result.stderr,
    }
    if verify_webp_result.returncode != 0:
        report["status"] = "failed-webp-alpha-verification"
        print(json.dumps(report, indent=2, sort_keys=True))
        return verify_webp_result.returncode

    if profile.requires_visual_qa and not args.visual_qa_pass:
        report["status"] = "requires-visual-qa"
        report["visual_qa_required_reason"] = (
            f"Quality profile {args.quality_profile!r} is relaxed and may hide edge artifacts. "
            "Inspect the staged PNG/WebP, then rerun with --visual-qa-pass to copy into examples."
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 3

    for key in ("black", "white", "green", "png", "webp", "report"):
        paths[key].parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(args.black, paths["black"])
    shutil.copy2(args.white, paths["white"])
    if args.green:
        shutil.copy2(args.green, paths["green"])
    elif paths["green"].exists() and args.force:
        paths["green"].unlink()
    shutil.copy2(stage_png, paths["png"])
    shutil.copy2(stage_webp, paths["webp"])

    report["status"] = "passed-relaxed-visual-qa" if profile.requires_visual_qa else "passed"
    report["final_paths"] = {key: str(path) for key, path in paths.items()}
    paths["report"].write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
