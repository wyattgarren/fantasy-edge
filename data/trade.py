"""Builds a live trade evaluation, combining Sleeper rosters with real
rest-of-season values (data/ros_value.py's player_ros_value, shared with
data/waiver.py) and core/trade.py.
"""

from __future__ import annotations

from core.trade import TradeEvaluation, evaluate_side, evaluate_trade
from core.waiver import RosValueBreakdown
from data.models import League, Player, Roster
from data.projections import SKILL_POSITIONS
from data.ros_value import RosContext, compute_vorp, load_ros_context, player_ros_value
from data.waiver import roster_need_by_position


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


def _handcuff_warnings(
    roster_positions: list[str],
    players: dict[str, Player],
    pre_trade_ros: dict[str, float],
    post_trade_ros: dict[str, float],
    schedules,
    week: int,
) -> list[str]:
    """Positions where this trade pushes the roster from fine to short a
    healthy starter -- a second, informational lens alongside the lineup-
    value verdict, not baked into it. Only flags positions whose deficit
    INCREASES; a side that was already short somewhere doesn't get a new
    warning every time for a pre-existing problem this trade didn't cause."""
    pre_need = roster_need_by_position(
        list(pre_trade_ros), players, pre_trade_ros, roster_positions, schedules, week
    )
    post_need = roster_need_by_position(
        list(post_trade_ros), players, post_trade_ros, roster_positions, schedules, week
    )
    warnings: list[str] = []
    for position, post in post_need.items():
        pre_deficit = pre_need[position].deficit if position in pre_need else 0
        if post.deficit > pre_deficit:
            warnings.append(
                f"short at {position} after this trade "
                f"({post.healthy_count} healthy for {post.required_starters} slots)"
            )
    return warnings


def build_trade_evaluation(
    league: League,
    rosters: list[Roster],
    my_roster: Roster,
    their_roster: Roster,
    players: dict[str, Player],
    gives: list[str],
    receives: list[str],
    season: str,
    week: int,
    demo: bool = False,
) -> tuple[TradeEvaluation, dict[str, RosValueBreakdown], dict[str, float], dict[str, list[str]]]:
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

    vorp_by_player = compute_vorp(ctx, rosters, players, league.roster_positions)
    trade_vorp = {pid: vorp_by_player.get(pid, 0.0) for pid in set(gives) | set(receives)}

    my_post_trade_ros = {pid: v for pid, v in my_values.items() if pid not in gives}
    my_post_trade_ros.update({pid: their_values[pid] for pid in receives})
    their_post_trade_ros = {pid: v for pid, v in their_values.items() if pid not in receives}
    their_post_trade_ros.update({pid: my_values[pid] for pid in gives})

    handcuff_warnings = {
        "you": _handcuff_warnings(
            league.roster_positions, players, my_values, my_post_trade_ros, ctx.schedules, week
        ),
        "them": _handcuff_warnings(
            league.roster_positions, players, their_values, their_post_trade_ros, ctx.schedules, week
        ),
    }

    return evaluation, breakdowns, trade_vorp, handcuff_warnings
