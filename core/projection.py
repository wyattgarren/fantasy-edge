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

# How much of a player's actual-vs-expected-fantasy-points gap (a ratio, e.g.
# +0.2 means they scored 20% more than nflverse's own expected-points model
# projected) to pull back toward 0 per game. 0.5 mirrors
# opportunity_adjustment's own philosophy of partial, not full, trust in a
# trend: beating expectation may reflect a genuinely expanded role, not just
# TD luck, so regress halfway, not all the way.
REGRESSION_PULL_FRACTION = 0.5

# Clamp on the same ratio, same spirit as opportunity_adjustment's 0.7/1.3
# clamp: caps how much a small early-season sample can swing the projection.
REGRESSION_MAX_RATIO = 0.5

# Vegas lines reflect real market expectations of how a game will be
# played. Empirically fit, not hand-picked -- see
# scripts/calibrate_game_script.py, which regresses each skill player's
# weekly PPR-points deviation from their own season average against the
# game's real spread/total across 2021-2025 (1,359 games; n=3,079-11,926
# player-weeks per position). Findings matched the research direction: a
# favorite protecting a lead runs more (RB-specific -- spread slope
# correlation 0.047, n=7,434), and a higher-total game means more overall
# scoring/passing opportunity for pass-catchers/QBs (total-line
# correlations 0.016-0.023) but NOT meaningfully for RBs specifically
# (correlation -0.002, indistinguishable from 0 -- zeroed out below rather
# than keeping noise). These correlations are intentionally small/real --
# this is a secondary nudge, not a primary signal.
NEUTRAL_TOTAL = 44.55  # empirical mean total_line across the calibration dataset
GAME_SCRIPT_SPREAD_CLAMP = 17.0  # observed team_spread range was -20.5..20.5; bounds extreme outlier lines
GAME_SCRIPT_TOTAL_CLAMP = 12.0   # observed total_line range was 28.5..57.5 (neutral +-~13..16)
GAME_SCRIPT_SPREAD_COEFFICIENT = 0.0423  # points per point of spread favor, RB only
GAME_SCRIPT_TOTAL_COEFFICIENTS: dict[str, float] = {
    "QB": 0.0364,
    "RB": 0.0,  # empirically ~0 -- total doesn't move RB production the way it does the passing game
    "WR": 0.0204,
    "TE": 0.0228,
}


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


def regression_adjustment(
    diff_ratio: float,
    baseline: float,
    weeks_played: int,
    shrinkage_full_weeks: int = 8,
    pull_fraction: float = REGRESSION_PULL_FRACTION,
    max_ratio: float = REGRESSION_MAX_RATIO,
) -> float:
    """Point delta pulling `baseline` toward nflverse's own expected-
    fantasy-points model when actual production has diverged from it
    (TD-rate/efficiency mean reversion), shrunk toward 0 early in the
    season when the sample is small.

    `diff_ratio` is (actual - expected) / expected over the player's prior
    games -- a ratio, not a raw point diff, since nflverse's expected-points
    model uses its own internal scoring assumptions, not this league's real
    scoring_settings. Applying the ratio to the already-correctly-scored
    `baseline` sidesteps ever reconciling the two scoring systems.
    """
    ratio = min(max(diff_ratio, -max_ratio), max_ratio)
    shrinkage = min(weeks_played / shrinkage_full_weeks, 1.0) if shrinkage_full_weeks > 0 else 1.0
    return -pull_fraction * ratio * baseline * shrinkage


def game_script_adjustment(
    position: str,
    team_spread: float,
    total_line: float,
    neutral_total: float = NEUTRAL_TOTAL,
    spread_clamp: float = GAME_SCRIPT_SPREAD_CLAMP,
    total_clamp: float = GAME_SCRIPT_TOTAL_CLAMP,
) -> float:
    """Point delta from this week's real Vegas spread/total (a game-script
    proxy) -- same calling convention as matchup_adjustment (a direct
    points delta, not baseline-scaled), since the calibration measured a
    direct points effect, not a ratio. `team_spread` is signed so positive
    always means the player's own team is favored."""
    spread_term = 0.0
    if position == "RB":
        clamped_spread = min(max(team_spread, -spread_clamp), spread_clamp)
        spread_term = GAME_SCRIPT_SPREAD_COEFFICIENT * clamped_spread

    total_coefficient = GAME_SCRIPT_TOTAL_COEFFICIENTS.get(position, 0.0)
    clamped_total_delta = min(max(total_line - neutral_total, -total_clamp), total_clamp)
    total_term = total_coefficient * clamped_total_delta

    return spread_term + total_term


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
