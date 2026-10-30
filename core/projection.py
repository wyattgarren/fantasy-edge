"""Transparent, testable fantasy-point projection for a single player/week.

Operates on plain numbers only (no nflreadpy/Sleeper objects) so every piece
is independently known-input -> known-output testable. data/stats.py is
responsible for turning real data into these numeric inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean, stdev

# z-score for the 20th/80th percentile of a normal distribution.
Z_80 = 0.8416212335729143

OUT_STATUSES = {"out", "ir", "injured reserve", "pup", "nfi", "suspended"}


@dataclass
class Projection:
    mean: float
    floor: float
    ceiling: float
    std: float
    components: dict[str, float] = field(default_factory=dict)


def baseline_points(
    weekly_points: list[float], recent_n: int = 3, recent_weight: float = 0.5
) -> float:
    """Weighted average of recent fantasy points vs. season-to-date."""
    if not weekly_points:
        return 0.0
    recent_avg = mean(weekly_points[-recent_n:])
    season_avg = mean(weekly_points)
    return recent_weight * recent_avg + (1 - recent_weight) * season_avg


def opportunity_adjustment(
    recent_share: float,
    season_share: float,
    baseline: float,
    min_ratio: float = 0.7,
    max_ratio: float = 1.3,
) -> float:
    """Point delta from a trending opportunity share (snap %/target/carry share).

    Rising opportunity (recent_share > season_share) adds points; the ratio is
    clamped so a tiny-sample trend can't swing the projection wildly.
    """
    if season_share <= 0:
        return 0.0
    ratio = recent_share / season_share
    ratio = min(max(ratio, min_ratio), max_ratio)
    return baseline * (ratio - 1)


def matchup_adjustment(
    opponent_points_allowed: float,
    league_avg_points_allowed: float,
    weeks_played: int,
    shrinkage_full_weeks: int = 8,
) -> float:
    """Point delta for facing a defense that allows more/less than average,
    shrunk toward 0 (average) early in the season when the sample is small.
    """
    if shrinkage_full_weeks <= 0:
        shrinkage = 1.0
    else:
        shrinkage = min(weeks_played / shrinkage_full_weeks, 1.0)
    effective_allowed = league_avg_points_allowed + shrinkage * (
        opponent_points_allowed - league_avg_points_allowed
    )
    return effective_allowed - league_avg_points_allowed


def availability_multiplier(
    status: str | None,
    is_bye: bool = False,
    questionable_discount: float = 0.85,
    doubtful_discount: float = 0.5,
) -> float:
    if is_bye:
        return 0.0
    normalized = (status or "").strip().lower()
    if normalized in OUT_STATUSES:
        return 0.0
    if normalized == "doubtful":
        return doubtful_discount
    if normalized == "questionable":
        return questionable_discount
    return 1.0


def project_player(
    weekly_points: list[float],
    recent_share: float,
    season_share: float,
    opponent_points_allowed: float,
    league_avg_points_allowed: float,
    weeks_played: int,
    status: str | None,
    is_bye: bool = False,
    recent_n: int = 3,
    recent_weight: float = 0.5,
    shrinkage_full_weeks: int = 8,
    questionable_discount: float = 0.85,
    doubtful_discount: float = 0.5,
) -> Projection:
    baseline = baseline_points(weekly_points, recent_n, recent_weight)
    opp_adj = opportunity_adjustment(recent_share, season_share, baseline)
    matchup_adj = matchup_adjustment(
        opponent_points_allowed, league_avg_points_allowed, weeks_played, shrinkage_full_weeks
    )
    pre_availability = max(0.0, baseline + opp_adj + matchup_adj)
    availability = availability_multiplier(
        status, is_bye, questionable_discount, doubtful_discount
    )
    mean_points = pre_availability * availability

    # Week-to-week variance comes from the player's own history; fall back to
    # a fraction of baseline when there's not enough history for a real stdev.
    if len(weekly_points) >= 2:
        std_raw = stdev(weekly_points)
    else:
        std_raw = baseline * 0.3
    std = std_raw * availability

    floor = max(0.0, mean_points - Z_80 * std)
    ceiling = mean_points + Z_80 * std

    components = {
        "baseline": baseline,
        "opportunity_adjustment": opp_adj,
        "matchup_adjustment": matchup_adj,
        "availability_multiplier": availability,
    }
    return Projection(
        mean=round(mean_points, 2),
        floor=round(floor, 2),
        ceiling=round(ceiling, 2),
        std=round(std, 2),
        components={k: round(v, 2) for k, v in components.items()},
    )
