"""Ranks waiver-wire targets with a transparent waiver score: rest-of-season
projection, positional need, and Sleeper trending adds. Pure math, no I/O --
data/waiver.py supplies the real numbers.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.projection import baseline_points, opportunity_adjustment

TRENDING_BONUS_TIERS = [(10, 3.0), (25, 1.5)]
TRENDING_BONUS_DEFAULT = 0.5

# Sleeper's standard bracket for this league (6-of-12 teams byes the top 2
# seeds in round 1, runs 3 rounds total); there's no explicit "number of
# playoff rounds" field in league.settings, and the real schedule's max week
# bounds this regardless of how many rounds we assume.
DEFAULT_PLAYOFF_ROUNDS = 3

# A trade's value is disproportionately about winning the fantasy playoffs,
# not the regular season -- weight playoff weeks 50% above a normal week.
PLAYOFF_WEEK_WEIGHT = 1.5

# position -> (age decline starts, decline per year past that age, floor
# multiplier so age alone never zeroes a player's value). Pre-peak ages
# intentionally get no bonus -- rising-opportunity players are already
# captured by opportunity_adjustment, and there's no clean citable "youth
# bonus" number to justify inventing one. See docs/ROADMAP.md-adjacent
# research notes: RB's 28->29 transition is a cited ~25% one-year PPG
# cliff; TE's is a cited "89% of baseline at 34"; WR/QB are fit to the
# qualitative research shape (longest/flattest and latest/slowest-declining
# positions respectively) since no equally clean single annual-rate number
# exists for them.
AGE_CURVES: dict[str, tuple[float, float, float]] = {
    "RB": (27.0, 0.08, 0.60),   # ~1/3 of the cited one-year cliff, applied
                                 # as an ongoing rate so one year's cliff
                                 # isn't quadruple-counted across a career
    "WR": (29.0, 0.04, 0.75),
    "TE": (32.0, 0.055, 0.80),  # reproduces "89% of baseline at 34"
    "QB": (34.0, 0.03, 0.85),
}


def position_age_multiplier(position: str | None, age: float | None) -> float:
    """1.0 if the position/age is unknown or the player hasn't reached that
    position's decline-start age yet; otherwise a linear decline, floored."""
    if age is None or position not in AGE_CURVES:
        return 1.0
    decline_start, decline_per_year, floor = AGE_CURVES[position]
    if age <= decline_start:
        return 1.0
    return max(floor, 1.0 - decline_per_year * (age - decline_start))


@dataclass
class RosValueBreakdown:
    baseline: float
    opportunity: float
    regression: float
    avg_matchup_adjustment: float
    age_multiplier: float
    availability_multiplier: float
    games_weight: float
    per_game: float
    total: float
    components: dict[str, float]


def ros_value(
    weekly_points: list[float],
    recent_share: float,
    season_share: float,
    week_weights: list[float],
    avg_matchup_adjustment: float = 0.0,
    regression_points_per_game: float = 0.0,
    age_multiplier: float = 1.0,
    availability_multiplier: float = 1.0,
    shrinkage_full_weeks: int = 4,
) -> RosValueBreakdown:
    """Rest-of-season value: a per-game estimate (recency-weighted baseline,
    opportunity trend, TD/efficiency regression, and average strength of
    remaining schedule) times a bye/playoff-weighted count of remaining
    games.

    The per-game estimate is shrunk toward 0 when there's only a game or two
    of history (same shrink-early-season idea as
    core.projection.matchup_adjustment) -- without this, a single huge game
    from an obscure player (e.g. one spot start) produces an absurd
    multi-week extrapolation. By `shrinkage_full_weeks` games of real
    history, it's trusted at full value.

    `week_weights` has one entry per remaining week (0.0 on a bye,
    `PLAYOFF_WEEK_WEIGHT` on a playoff week, else 1.0). `availability_
    multiplier` -- the player's *current* injury status -- is applied only
    to `week_weights[0]` (the next upcoming week), not the whole season:
    Sleeper's injury_status is a snapshot of right now, and assuming a
    Questionable/Out tag means missing every remaining week through the
    playoffs would be a new, different correctness bug. The bye dimension
    is already fully represented as 0.0 entries in `week_weights` itself.
    """
    baseline = baseline_points(weekly_points)
    opportunity = opportunity_adjustment(recent_share, season_share, baseline)
    raw = baseline + opportunity + regression_points_per_game + avg_matchup_adjustment
    shrinkage = min(len(weekly_points) / shrinkage_full_weeks, 1.0) if shrinkage_full_weeks > 0 else 1.0
    per_game = max(0.0, raw * shrinkage * age_multiplier)

    weighted_weeks = list(week_weights)
    if weighted_weeks:
        weighted_weeks[0] *= availability_multiplier
    games_weight = sum(weighted_weeks)

    total = per_game * games_weight

    components = {
        "baseline": baseline,
        "opportunity": opportunity,
        "regression": regression_points_per_game,
        "matchup_adjustment": avg_matchup_adjustment,
        "age_multiplier": age_multiplier,
        "availability_multiplier": availability_multiplier,
        "games_weight": games_weight,
        "per_game": per_game,
        "total": total,
    }
    return RosValueBreakdown(
        baseline=baseline,
        opportunity=opportunity,
        regression=regression_points_per_game,
        avg_matchup_adjustment=avg_matchup_adjustment,
        age_multiplier=age_multiplier,
        availability_multiplier=availability_multiplier,
        games_weight=games_weight,
        per_game=per_game,
        total=total,
        components={k: round(v, 2) for k, v in components.items()},
    )


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
