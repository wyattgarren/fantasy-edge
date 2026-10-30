"""Builds a live trade evaluation, combining Sleeper rosters with real
rest-of-season values (data/ros_value.py's player_ros_value, shared with
data/waiver.py) and core/trade.py.
"""

from __future__ import annotations

from core.trade import TradeEvaluation, evaluate_side, evaluate_trade
from core.waiver import RosValueBreakdown
from data.models import League, Player, Roster
from data.projections import SKILL_POSITIONS
from data.ros_value import RosContext, load_ros_context, player_ros_value


def _roster_positions_and_breakdowns(
    roster: Roster,
    players: dict[str, Player],
    ctx: RosContext,
) -> tuple[dict[str, str], dict[str, RosValueBreakdown]]:
    positions: dict[str, str] = {}
    breakdowns: dict[str, RosValueBreakdown] = {}
    for player_id in roster.players:
        player = players.get(player_id)
        if player is None or player.position not in SKILL_POSITIONS:
            continue
        positions[player_id] = player.position
        breakdowns[player_id] = player_ros_value(ctx, player, player_id)
    return positions, breakdowns


def build_trade_evaluation(
    league: League,
    my_roster: Roster,
    their_roster: Roster,
    players: dict[str, Player],
    gives: list[str],
    receives: list[str],
    season: str,
    week: int,
    demo: bool = False,
) -> tuple[TradeEvaluation, dict[str, RosValueBreakdown]]:
    ctx = load_ros_context(league, season, week, demo=demo)

    my_positions, my_breakdowns = _roster_positions_and_breakdowns(my_roster, players, ctx)
    their_positions, their_breakdowns = _roster_positions_and_breakdowns(
        their_roster, players, ctx
    )
    my_values = {pid: b.total for pid, b in my_breakdowns.items()}
    their_values = {pid: b.total for pid, b in their_breakdowns.items()}

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

    evaluation = evaluate_trade(my_result, their_result)
    breakdowns = {
        **{pid: my_breakdowns[pid] for pid in gives},
        **{pid: their_breakdowns[pid] for pid in receives},
    }
    return evaluation, breakdowns
