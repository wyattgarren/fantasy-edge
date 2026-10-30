"""Builds a live trade evaluation, combining Sleeper rosters with real
rest-of-season values (core/waiver.py's ros_value, via the same feature
extraction data/waiver.py uses) and core/trade.py.
"""

from __future__ import annotations

import data.stats as stats
from core.trade import TradeEvaluation, evaluate_side, evaluate_trade
from core.waiver import ros_value
from data.models import League, Player, Roster
from data.projections import SKILL_POSITIONS


def _roster_positions_and_values(
    roster: Roster,
    players: dict[str, Player],
    weekly_points,
    opportunity,
    sleeper_to_gsis: dict[str, str | None],
    week: int,
    remaining_weeks: int,
) -> tuple[dict[str, str], dict[str, float]]:
    positions: dict[str, str] = {}
    values: dict[str, float] = {}
    for player_id in roster.players:
        player = players.get(player_id)
        if player is None or player.position not in SKILL_POSITIONS:
            continue
        weekly_points_list, recent_share, season_share = stats.player_weekly_points_and_shares(
            player_id, weekly_points, opportunity, sleeper_to_gsis, week
        )
        positions[player_id] = player.position
        values[player_id] = ros_value(weekly_points_list, recent_share, season_share, remaining_weeks)
    return positions, values


def build_trade_evaluation(
    league: League,
    my_roster: Roster,
    their_roster: Roster,
    players: dict[str, Player],
    gives: list[str],
    receives: list[str],
    season: str,
    week: int,
) -> TradeEvaluation:
    remaining_weeks = max(int(league.settings.get("playoff_week_start") or week + 1) - week, 1)

    weekly_stats = stats.load_weekly_stats(season)
    weekly_points = stats.weekly_fantasy_points(weekly_stats, league.scoring_settings)
    snap_counts = stats.load_snap_counts(season)
    id_map = stats.load_player_id_map()
    opportunity = stats.opportunity_shares(weekly_stats, snap_counts, id_map)
    sleeper_to_gsis = dict(zip(id_map["sleeper_id"].to_list(), id_map["gsis_id"].to_list()))

    my_positions, my_values = _roster_positions_and_values(
        my_roster, players, weekly_points, opportunity, sleeper_to_gsis, week, remaining_weeks
    )
    their_positions, their_values = _roster_positions_and_values(
        their_roster, players, weekly_points, opportunity, sleeper_to_gsis, week, remaining_weeks
    )

    my_result = evaluate_side(
        league.roster_positions,
        my_positions,
        my_values,
        gives=gives,
        receives=receives,
        received_positions={pid: their_positions[pid] for pid in receives},
        received_ros_values={pid: their_values[pid] for pid in receives},
    )
    their_result = evaluate_side(
        league.roster_positions,
        their_positions,
        their_values,
        gives=receives,
        receives=gives,
        received_positions={pid: my_positions[pid] for pid in gives},
        received_ros_values={pid: my_values[pid] for pid in gives},
    )

    return evaluate_trade(my_result, their_result)
