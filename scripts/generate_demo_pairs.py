#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from quality_profiles import get_profile, profile_names


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
DEFAULT_MANIFEST = REPO_DIR / "examples" / "demo_prompts.json"
DEFAULT_EXAMPLES_DIR = REPO_DIR / "examples"


BLACK_EXTRACTION_PROMPT = """Extraction role: first black-background source image.
Create the requested asset on a perfectly flat solid #000000 background for black/white alpha extraction.
The background must be one uniform black color with no shadows, gradients, texture, reflections, floor plane, environment, vignette, or lighting variation.
Keep every subject fully separated from the background with crisp edges and generous padding.
No cast shadow, no contact shadow, no reflection, no checkerboard, no watermark, and no text unless explicitly requested by the asset prompt.
Output an opaque PNG."""


WHITE_REFERENCE_PROMPT = """Use the provided input image as the first-image reference target.
Generate a second image that changes only the background from pure black #000000 to pure white #ffffff.
Do not change the subject, pose, scale, crop, camera, lighting, colors, edges, shadows, materials, pixels, placement, or image dimensions.
The output must be identical to the input except the background color is #ffffff.
Do not create an independent composition. No new objects, no text, no watermark, no checkerboard. Output an opaque PNG."""


def default_image_gen_cli() -> Path:
    if os.environ.get("ALPHAKIT_IMAGE_GEN"):
        return Path(os.environ["ALPHAKIT_IMAGE_GEN"])
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    return codex_home / "skills" / "imagegen" / "scripts" / "image_gen.py"


def read_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    demos = data.get("demos")
    if not isinstance(demos, list) or not demos:
        raise SystemExit(f"No demos found in manifest: {path}")
    for demo in demos:
        for key in ("id", "title", "size", "prompt"):
            if key not in demo or not str(demo[key]).strip():
                raise SystemExit(f"Demo entry missing {key}: {demo}")
    return demos


def select_demos(demos: list[dict[str, Any]], requested: list[str] | None) -> list[dict[str, Any]]:
    if not requested:
        return demos
    by_id = {demo["id"]: demo for demo in demos}
    missing = [demo_id for demo_id in requested if demo_id not in by_id]
    if missing:
        raise SystemExit(f"Unknown demo id(s): {', '.join(missing)}")
    return [by_id[demo_id] for demo_id in requested]


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)


def parse_json_output(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = result.stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw_stdout": stdout}


def image_size(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "Pillow is required to read the first generated image size. "
            "Run with `uv run --with pillow python` or install Pillow."
        ) from exc

    with Image.open(path) as image:
        return image.size


def image_size_label(path: Path) -> str:
    width, height = image_size(path)
    return f"{width}x{height}"


def default_image_gen_runner() -> list[str]:
    uv = shutil.which("uv")
    if uv:
        return [uv, "run", "--with", "openai", "--with", "pillow", "python"]
    return [sys.executable]


def image_gen_generate_command(
    runner: list[str],
    image_gen_cli: Path,
    *,
    prompt: str,
    out: Path,
    size: str,
) -> list[str]:
    return [
        *runner,
        str(image_gen_cli),
        "generate",
        "--prompt",
        prompt,
        "--size",
        size,
        "--quality",
        "high",
        "--background",
        "opaque",
        "--output-format",
        "png",
        "--out",
        str(out),
        "--force",
        "--no-augment",
    ]


def responses_reference_command(
    runner: list[str],
    *,
    prompt: str,
    reference_image: Path,
    out: Path,
    size: str,
    response_model: str,
    image_model: str,
) -> list[str]:
    return [
        *runner,
        str(SCRIPT_DIR / "responses_reference_generate.py"),
        "--reference-image",
        str(reference_image),
        "--prompt",
        prompt,
        "--out",
        str(out),
        "--size",
        size,
        "--response-model",
        response_model,
        "--image-model",
        image_model,
    ]


def build_black_prompt(demo: dict[str, Any]) -> str:
    return f"{demo['prompt']}\n\n{BLACK_EXTRACTION_PROMPT}"


def build_white_prompt(_demo: dict[str, Any]) -> str:
    return WHITE_REFERENCE_PROMPT


def final_paths(examples_dir: Path, demo_id: str) -> dict[str, Path]:
    return {
        "black": examples_dir / "pairs" / f"{demo_id}-black.png",
        "white": examples_dir / "pairs" / f"{demo_id}-white.png",
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


def copy_passed_demo(stage: dict[str, Path], final: dict[str, Path], report: dict[str, Any]) -> None:
    for key in ("black", "white", "png", "webp"):
        final[key].parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stage[key], final[key])
    final["report"].parent.mkdir(parents=True, exist_ok=True)
    final["report"].write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_demo(
    demo: dict[str, Any],
    *,
    args: argparse.Namespace,
    run_dir: Path,
) -> dict[str, Any]:
    demo_id = str(demo["id"])
    demo_dir = run_dir / demo_id
    stage = {
        "black": demo_dir / f"{demo_id}-black.png",
        "white": demo_dir / f"{demo_id}-white.png",
        "png": demo_dir / f"{demo_id}.png",
        "webp": demo_dir / f"{demo_id}.webp",
    }
    report_path = demo_dir / f"{demo_id}.json"
    final = final_paths(args.examples_dir, demo_id)

    black_prompt = build_black_prompt(demo)
    white_prompt = build_white_prompt(demo)
    generate_black = image_gen_generate_command(
        args.image_gen_runner_command,
        args.image_gen_cli,
        prompt=black_prompt,
        out=stage["black"],
        size=str(demo["size"]),
    )

    plan = {
        "id": demo_id,
        "title": demo["title"],
        "requested_black_size": demo["size"],
        "reference_white_size_source": "actual black image dimensions after generation",
        "stage_paths": {key: str(path) for key, path in stage.items()},
        "final_paths": {key: str(path) for key, path in final.items()},
        "commands": {
            "generate_black": generate_black,
        },
    }
    if args.dry_run:
        return {"id": demo_id, "status": "dry-run", "plan": plan}

    ensure_no_overwrite(final, args.force)
    demo_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "id": demo_id,
        "title": demo["title"],
        "requested_black_size": demo["size"],
        "prompt": demo["prompt"],
        "black_prompt": black_prompt,
        "white_reference_prompt": white_prompt,
        "stage_paths": {key: str(path) for key, path in stage.items()},
        "final_paths": {key: str(path) for key, path in final.items()},
        "commands": plan["commands"],
        "status": "started",
    }

    black_result = run(generate_black, cwd=REPO_DIR)
    result["generate_black"] = {
        "returncode": black_result.returncode,
        "stdout": black_result.stdout,
        "stderr": black_result.stderr,
    }
    if black_result.returncode != 0:
        result["status"] = "failed-generate-black"
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    actual_black_size = image_size_label(stage["black"])
    result["actual_black_size"] = actual_black_size
    reference_generate_white = responses_reference_command(
        args.image_gen_runner_command,
        prompt=white_prompt,
        reference_image=stage["black"],
        out=stage["white"],
        size=actual_black_size,
        response_model=args.response_model,
        image_model=args.image_model,
    )
    result["commands"]["reference_generate_white"] = reference_generate_white

    white_result = run(reference_generate_white, cwd=REPO_DIR)
    result["reference_generate_white"] = {
        "returncode": white_result.returncode,
        "stdout": white_result.stdout,
        "stderr": white_result.stderr,
    }
    if white_result.returncode != 0:
        result["status"] = "failed-reference-generate-white"
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    actual_white_size = image_size_label(stage["white"])
    result["actual_white_size"] = actual_white_size
    if actual_white_size != actual_black_size:
        result["status"] = "failed-reference-size-mismatch"
        result["size_mismatch"] = {
            "black": actual_black_size,
            "white": actual_white_size,
            "reason": "Strict black/white extraction requires identical image dimensions.",
        }
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    extract_command = [
        sys.executable,
        str(SCRIPT_DIR / "alpha_from_black_white.py"),
        "--black",
        str(stage["black"]),
        "--white",
        str(stage["white"]),
        "--out",
        str(stage["png"]),
        "--quality-profile",
        args.quality_profile,
        "--json",
    ]
    extract_result = run(extract_command, cwd=REPO_DIR)
    result["commands"]["extract_alpha"] = extract_command
    result["extract_alpha"] = {
        "returncode": extract_result.returncode,
        "report": parse_json_output(extract_result),
        "stderr": extract_result.stderr,
    }
    if extract_result.returncode != 0:
        result["status"] = "failed-strict-extraction"
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    verify_png_command = [
        sys.executable,
        str(SCRIPT_DIR / "verify_alpha.py"),
        str(stage["png"]),
        "--json",
    ]
    verify_png_result = run(verify_png_command, cwd=REPO_DIR)
    result["commands"]["verify_png"] = verify_png_command
    result["verify_png"] = {
        "returncode": verify_png_result.returncode,
        "report": parse_json_output(verify_png_result),
        "stderr": verify_png_result.stderr,
    }
    if verify_png_result.returncode != 0:
        result["status"] = "failed-png-alpha-verification"
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    export_webp_command = [
        sys.executable,
        str(SCRIPT_DIR / "export_image.py"),
        "--input",
        str(stage["png"]),
        "--format",
        "webp",
        "--out",
        str(stage["webp"]),
        "--preserve-alpha",
        "--lossless",
        "--json",
    ]
    export_webp_result = run(export_webp_command, cwd=REPO_DIR)
    result["commands"]["export_webp"] = export_webp_command
    result["export_webp"] = {
        "returncode": export_webp_result.returncode,
        "report": parse_json_output(export_webp_result),
        "stderr": export_webp_result.stderr,
    }
    if export_webp_result.returncode != 0:
        result["status"] = "failed-webp-export"
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    verify_webp_command = [
        sys.executable,
        str(SCRIPT_DIR / "verify_alpha.py"),
        str(stage["webp"]),
        "--json",
    ]
    verify_webp_result = run(verify_webp_command, cwd=REPO_DIR)
    result["commands"]["verify_webp"] = verify_webp_command
    result["verify_webp"] = {
        "returncode": verify_webp_result.returncode,
        "report": parse_json_output(verify_webp_result),
        "stderr": verify_webp_result.stderr,
    }
    if verify_webp_result.returncode != 0:
        result["status"] = "failed-webp-alpha-verification"
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    profile = get_profile(args.quality_profile)
    result["quality_profile"] = args.quality_profile
    result["visual_qa_required"] = profile.requires_visual_qa
    result["visual_qa_passed"] = args.visual_qa_pass
    result["visual_qa_note"] = args.visual_qa_note
    if profile.requires_visual_qa and not args.visual_qa_pass:
        result["status"] = "requires-visual-qa"
        result["visual_qa_required_reason"] = (
            f"Quality profile {args.quality_profile!r} is relaxed and may hide edge artifacts. "
            "Inspect the staged PNG/WebP, then rerun with --visual-qa-pass to copy into examples."
        )
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result

    result["status"] = "passed-relaxed-visual-qa" if profile.requires_visual_qa else "passed"
    copy_passed_demo(stage, final, result)
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Alphakit demo black/white pairs, strict-extract alpha, "
            "and add only demos that pass."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--examples-dir", type=Path, default=DEFAULT_EXAMPLES_DIR)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--image-gen-cli", type=Path, default=default_image_gen_cli())
    parser.add_argument("--response-model", default=os.environ.get("ALPHAKIT_RESPONSE_MODEL", "gpt-5.4"))
    parser.add_argument("--image-model", default=os.environ.get("ALPHAKIT_IMAGE_MODEL", "gpt-image-1.5"))
    parser.add_argument(
        "--image-gen-runner",
        help=(
            "Command prefix for running image_gen.py. Defaults to "
            "`uv run --with openai --with pillow python` when uv is installed."
        ),
    )
    parser.add_argument("--python", help="Shortcut for --image-gen-runner '<python>'.")
    parser.add_argument("--only", action="append", help="Demo id to run. Repeat for multiple.")
    parser.add_argument("--quality-profile", choices=profile_names(), default="strict")
    parser.add_argument("--visual-qa-pass", action="store_true")
    parser.add_argument("--visual-qa-note", default="")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    args.manifest = args.manifest.resolve()
    args.examples_dir = args.examples_dir.resolve()
    args.image_gen_cli = args.image_gen_cli.resolve()
    if args.image_gen_runner:
        args.image_gen_runner_command = shlex.split(args.image_gen_runner)
    elif args.python:
        args.image_gen_runner_command = [args.python]
    else:
        args.image_gen_runner_command = default_image_gen_runner()
    run_dir = (
        args.run_dir.resolve()
        if args.run_dir
        else Path(tempfile.gettempdir()) / f"alphakit-demo-pairs-{time.strftime('%Y%m%d-%H%M%S')}"
    )

    demos = select_demos(read_manifest(args.manifest), args.only)

    if not args.dry_run:
        if not args.image_gen_cli.exists():
            raise SystemExit(
                f"Image generation CLI not found: {args.image_gen_cli}. "
                "Install the imagegen skill or pass --image-gen-cli."
            )
        if not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit(
                "OPENAI_API_KEY is not set. Demo generation requires the imagegen CLI "
                "to call OpenAI images.generate for the black image and Responses "
                "image_generation with the black image as the reference target."
            )

    results = [run_demo(demo, args=args, run_dir=run_dir) for demo in demos]
    summary = {
        "run_dir": str(run_dir),
        "selected": [demo["id"] for demo in demos],
        "passed": [
            result["id"]
            for result in results
            if result["status"] in {"passed", "passed-relaxed-visual-qa"}
        ],
        "failed": [
            {"id": result["id"], "status": result["status"]}
            for result in results
            if result["status"] not in {"passed", "passed-relaxed-visual-qa", "dry-run"}
        ],
        "dry_run": args.dry_run,
    }
    print(json.dumps({"summary": summary, "results": results}, indent=2, sort_keys=True))

    if args.dry_run:
        return 0
    return 0 if summary["passed"] else 4


if __name__ == "__main__":
    sys.exit(main())
