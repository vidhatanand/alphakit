from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class QualityProfile:
    name: str
    max_spread_p95: float
    max_spread_p99: float
    max_spread_max: float
    max_negative_ratio: float
    max_too_high_ratio: float = 0.0
    snap_alpha_below: int = 0
    requires_visual_qa: bool = False
    description: str = ""


QUALITY_PROFILES: dict[str, QualityProfile] = {
    "strict": QualityProfile(
        name="strict",
        max_spread_p95=0.12,
        max_spread_p99=0.015,
        max_spread_max=0.12,
        max_negative_ratio=0.03,
        snap_alpha_below=20,
        description="Default extraction gate for committed demo assets.",
    ),
    "soft-photoreal": QualityProfile(
        name="soft-photoreal",
        max_spread_p95=0.18,
        max_spread_p99=0.10,
        max_spread_max=0.35,
        max_negative_ratio=0.18,
        snap_alpha_below=12,
        requires_visual_qa=True,
        description=(
            "Opt-in relaxed gate for photoreal hair, soft shadows, glass, smoke, "
            "or other semitransparent edges. Requires visual QA before demos are copied."
        ),
    ),
    "game-sprite": QualityProfile(
        name="game-sprite",
        max_spread_p95=0.28,
        max_spread_p99=0.36,
        max_spread_max=0.70,
        max_negative_ratio=0.20,
        snap_alpha_below=40,
        requires_visual_qa=True,
        description=(
            "Opt-in relaxed gate for generated game sprites, icon sheets, portrait packs, "
            "and VFX frames where Codex reference generation preserves layout but changes "
            "edge/background pixels. Requires visual QA before demos are copied."
        ),
    ),
}


def profile_names() -> tuple[str, ...]:
    return tuple(QUALITY_PROFILES)


def get_profile(name: str) -> QualityProfile:
    try:
        return QUALITY_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown quality profile: {name}") from exc


def resolve_thresholds(
    *,
    profile_name: str,
    max_spread_p95: float | None = None,
    max_spread_p99: float | None = None,
    max_spread_max: float | None = None,
    max_negative_ratio: float | None = None,
    max_too_high_ratio: float | None = None,
) -> dict[str, float]:
    profile = get_profile(profile_name)
    return {
        "max_spread_p95": profile.max_spread_p95
        if max_spread_p95 is None
        else max_spread_p95,
        "max_spread_p99": profile.max_spread_p99
        if max_spread_p99 is None
        else max_spread_p99,
        "max_spread_max": profile.max_spread_max
        if max_spread_max is None
        else max_spread_max,
        "max_negative_ratio": profile.max_negative_ratio
        if max_negative_ratio is None
        else max_negative_ratio,
        "max_too_high_ratio": profile.max_too_high_ratio
        if max_too_high_ratio is None
        else max_too_high_ratio,
    }


def profile_report(profile_name: str, thresholds: dict[str, float]) -> dict[str, object]:
    profile = get_profile(profile_name)
    data = asdict(profile)
    data["thresholds"] = dict(thresholds)
    return data


def resolve_snap_alpha_below(profile_name: str, snap_alpha_below: int | None = None) -> int:
    profile = get_profile(profile_name)
    return profile.snap_alpha_below if snap_alpha_below is None else snap_alpha_below


def passes_thresholds(report: dict[str, object], thresholds: dict[str, float]) -> bool:
    return (
        float(report["channel_spread_p95"]) <= thresholds["max_spread_p95"]
        and float(report["channel_spread_p99"]) <= thresholds["max_spread_p99"]
        and float(report["channel_spread_max"]) <= thresholds["max_spread_max"]
        and float(report["negative_diff_ratio"]) <= thresholds["max_negative_ratio"]
        and float(report["too_high_diff_ratio"]) <= thresholds["max_too_high_ratio"]
    )
