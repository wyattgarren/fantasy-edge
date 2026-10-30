"""Ranks waiver-wire targets with a transparent waiver score: rest-of-season
projection, positional need, and Sleeper trending adds. Pure math, no I/O --
data/waiver.py supplies the real numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.projection import baseline_points, opportunity_adjustment

TRENDING_BONUS_TIERS = [(10, 3.0), (25, 1.5)]
TRENDING_BONUS_DEFAULT = 0.5


def ros_value(
    weekly_points: list[float],
    recent_share: float,
    season_share: float,
    remaining_weeks: int,
    shrinkage_full_weeks: int = 4,
) -> float:
    """Rest-of-season value: a per-game estimate (recency-weighted baseline
    plus opportunity trend -- no per-future-week matchup, since opponents
    5+ weeks out aren't a meaningful signal) times games remaining.

    The per-game estimate is shrunk toward 0 when there's only a game or two
    of history (same shrink-early-season idea as
    core.projection.matchup_adjustment) -- without this, a single huge game
    from an obscure player (e.g. one spot start) produces an absurd 7-week
    extrapolation. By `shrinkage_full_weeks` games of real history, it's
    trusted at full value.
    """
    baseline = baseline_points(weekly_points)
    per_game_raw = max(
        0.0, baseline + opportunity_adjustment(recent_share, season_share, baseline)
    )
    shrinkage = min(len(weekly_points) / shrinkage_full_weeks, 1.0) if shrinkage_full_weeks > 0 else 1.0
    per_game = per_game_raw * shrinkage
    return per_game * max(remaining_weeks, 0)


@dataclass
class NeedBreakdown:
    deficit: int
    upcoming_byes: int
    score: float


def need_score(required_starters: int, healthy_count: int, upcoming_byes: int) -> NeedBreakdown:
    deficit = max(0, required_starters - healthy_count)
    score = deficit * 10.0 + upcoming_byes * 2.0
    return NeedBreakdown(deficit=deficit, upcoming_byes=upcoming_byes, score=score)


def trending_bonus(rank: int | None) -> float:
    if rank is None:
        return 0.0
    for cutoff, bonus in TRENDING_BONUS_TIERS:
        if rank <= cutoff:
            return bonus
    return TRENDING_BONUS_DEFAULT


@dataclass
class WaiverTarget:
    player_id: str
    ros_value: float
    need_bonus: float
    trending_bonus: float
    score: float
    suggested_drop_player_id: str | None = None
    bid_low: float | None = None
    bid_high: float | None = None


def suggest_drop(
    candidates: list[tuple[str, str, float]], roster_positions: list[str]
) -> str | None:
    """candidates: (player_id, position, ros_value) for every rostered
    skill-position player. Returns the lowest-ros_value player among
    positions where you have more rostered players than starting slots
    (a "surplus" position) -- not necessarily the same position as the add.
    """
    required_by_position: dict[str, int] = {}
    for pos in roster_positions:
        required_by_position[pos] = required_by_position.get(pos, 0) + 1

    counts: dict[str, int] = {}
    for _, position, _ in candidates:
        counts[position] = counts.get(position, 0) + 1

    surplus_positions = {
        pos
        for pos, count in counts.items()
        if count > required_by_position.get(pos, 0)
    }

    surplus_candidates = [c for c in candidates if c[1] in surplus_positions]
    if not surplus_candidates:
        return None
    return min(surplus_candidates, key=lambda c: c[2])[0]


def bid_percent_range(
    value_percentile: float, teams_needing: int, total_teams: int
) -> tuple[float, float]:
    """value_percentile in [0, 1] (this player's rank within the ranked
    free-agent pool); competition_factor in [0, 1] (share of other teams
    that show need at this position)."""
    base = 3.0 + value_percentile * 17.0
    competition_factor = teams_needing / total_teams if total_teams > 0 else 0.0
    low = base * (0.8 + 0.4 * competition_factor)
    high = base * (1.2 + 0.6 * competition_factor)
    return max(0.0, min(100.0, low)), max(0.0, min(100.0, high))
