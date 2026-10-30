"""The single shared assembly point for a player's rest-of-season value,
combining Sleeper (roster/injury status) with nflreadpy (data/stats.py) and
core/waiver.py's ros_value model. Both data/waiver.py and data/trade.py call
this instead of duplicating per-player feature extraction (the exact
duplication data/stats.py's player_weekly_points_and_shares docstring
already documents was fixed once before, for a smaller feature set).
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

import data.stats as stats
from core.projection import availability_multiplier, baseline_points, regression_adjustment
from core.waiver import DEFAULT_PLAYOFF_ROUNDS, RosValueBreakdown, position_age_multiplier, ros_value
from data.models import League, Player


@dataclass
class RosContext:
    weekly_points: pl.DataFrame
    points_allowed: pl.DataFrame
    opportunity: pl.DataFrame
    schedules: pl.DataFrame
    expected_points: pl.DataFrame
    player_ages: dict[str, float]
    sleeper_to_gsis: dict[str, str | None]
    week: int
    last_fantasy_week: int
    playoff_week_start: int


def load_ros_context(league: League, season: str, week: int, demo: bool = False) -> RosContext:
    weekly_stats = stats.load_weekly_stats(season, demo=demo)
    weekly_points = stats.weekly_fantasy_points(weekly_stats, league.scoring_settings)
    points_allowed = stats.points_allowed_by_position(weekly_points)
    snap_counts = stats.load_snap_counts(season, demo=demo)
    id_map = stats.load_player_id_map(demo=demo)
    opportunity = stats.opportunity_shares(weekly_stats, snap_counts, id_map)
    schedules = stats.load_schedules(season, demo=demo)
    expected_points = stats.load_expected_points(season, demo=demo)
    player_ages_df = stats.load_player_ages(demo=demo)

    sleeper_to_gsis = dict(zip(id_map["sleeper_id"].to_list(), id_map["gsis_id"].to_list()))
    player_ages = dict(
        zip(player_ages_df["sleeper_id"].to_list(), player_ages_df["age"].to_list())
    )

    playoff_week_start = int(league.settings.get("playoff_week_start") or week + 1)
    schedule_max_week = int(schedules["week"].max()) if schedules.height > 0 else week
    last_fantasy_week = max(
        min(playoff_week_start + DEFAULT_PLAYOFF_ROUNDS - 1, schedule_max_week), week
    )

    return RosContext(
        weekly_points=weekly_points,
        points_allowed=points_allowed,
        opportunity=opportunity,
        schedules=schedules,
        expected_points=expected_points,
        player_ages=player_ages,
        sleeper_to_gsis=sleeper_to_gsis,
        week=week,
        last_fantasy_week=last_fantasy_week,
        playoff_week_start=playoff_week_start,
    )


def player_ros_value(ctx: RosContext, player: Player, player_id: str) -> RosValueBreakdown:
    weekly_points_list, recent_share, season_share = stats.player_weekly_points_and_shares(
        player_id, ctx.weekly_points, ctx.opportunity, ctx.sleeper_to_gsis, ctx.week
    )
    weeks_played = len(weekly_points_list)
    team = player.team

    # The remaining-weeks window starts AT ctx.week (inclusive) -- the
    # current week's own game hasn't been used as training data above
    # (player_weekly_points_and_shares already filters week < ctx.week) and
    # is still upcoming, same convention data/projections.py uses when it
    # projects week=nfl_state.week as the next game to be played.
    if team is None:
        week_weights: list[float] = []
        avg_matchup_adjustment = 0.0
    else:
        week_weights = stats.remaining_week_weights(
            ctx.schedules, team, ctx.week, ctx.last_fantasy_week, ctx.playoff_week_start
        )
        _, avg_matchup_adjustment = stats.remaining_weeks_and_matchup_adjustment(
            ctx.schedules,
            ctx.points_allowed,
            team,
            player.position,
            weeks_played,
            ctx.week,
            ctx.last_fantasy_week,
            ctx.week,
        )

    gsis_id = ctx.sleeper_to_gsis.get(player_id)
    diff_ratio = stats.expected_points_diff_ratio(ctx.expected_points, gsis_id, ctx.week)
    regression_points_per_game = 0.0
    if diff_ratio is not None:
        baseline = baseline_points(weekly_points_list)
        regression_points_per_game = regression_adjustment(diff_ratio, baseline, weeks_played)

    age = ctx.player_ages.get(player_id)
    age_mult = position_age_multiplier(player.position, age)

    availability = availability_multiplier(player.injury_status)

    return ros_value(
        weekly_points=weekly_points_list,
        recent_share=recent_share,
        season_share=season_share,
        week_weights=week_weights,
        avg_matchup_adjustment=avg_matchup_adjustment,
        regression_points_per_game=regression_points_per_game,
        age_multiplier=age_mult,
        availability_multiplier=availability,
    )
