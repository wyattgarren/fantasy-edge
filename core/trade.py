"""Evaluates a trade: rest-of-season value change plus each side's starting
-lineup change (does it improve your best lineup, not just your total?).
Pure math, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.lineup import optimal_lineup
from core.projection import Projection


@dataclass
class TradeSideResult:
    value_change: float
    lineup_value_before: float
    lineup_value_after: float
    lineup_value_change: float


@dataclass
class TradeEvaluation:
    my_result: TradeSideResult
    their_result: TradeSideResult
    verdict: str
    reason: str


def _lineup_total_value(
    roster_positions: list[str], player_positions: dict[str, str], ros_values: dict[str, float]
) -> float:
    # optimal_lineup() ranks by Projection floor/ceiling via a risk slider;
    # ros_value is a single point estimate, so feed it in as a degenerate
    # Projection (floor == ceiling == mean) rather than adding a parallel
    # "rank by flat value" code path to core/lineup.py.
    fake_projections = {
        pid: Projection(mean=v, floor=v, ceiling=v, std=0.0, components={})
        for pid, v in ros_values.items()
    }
    return optimal_lineup(roster_positions, player_positions, fake_projections, risk=0.5).total_value


def evaluate_side(
    roster_positions: list[str],
    current_positions: dict[str, str],
    current_ros_values: dict[str, float],
    gives: list[str],
    receives: list[str],
    received_positions: dict[str, str],
    received_ros_values: dict[str, float],
) -> TradeSideResult:
    lineup_before = _lineup_total_value(roster_positions, current_positions, current_ros_values)

    new_positions = {pid: pos for pid, pos in current_positions.items() if pid not in gives}
    new_positions.update(received_positions)
    new_values = {pid: v for pid, v in current_ros_values.items() if pid not in gives}
    new_values.update(received_ros_values)

    lineup_after = _lineup_total_value(roster_positions, new_positions, new_values)

    value_change = sum(received_ros_values.get(pid, 0.0) for pid in receives) - sum(
        current_ros_values.get(pid, 0.0) for pid in gives
    )

    return TradeSideResult(
        value_change=value_change,
        lineup_value_before=lineup_before,
        lineup_value_after=lineup_after,
        lineup_value_change=lineup_after - lineup_before,
    )


def evaluate_trade(my_result: TradeSideResult, their_result: TradeSideResult) -> TradeEvaluation:
    if my_result.lineup_value_change > 0:
        verdict = "Accept"
        reason = f"Your starting lineup improves by {my_result.lineup_value_change:.1f} ROS pts."
    elif my_result.value_change > 0:
        verdict = "Counter"
        reason = (
            "You gain rest-of-season value but it doesn't improve your starting lineup -- "
            "ask for a piece that actually fills a starting spot."
        )
    elif my_result.lineup_value_change < 0:
        verdict = "Decline"
        reason = f"Your starting lineup gets worse by {abs(my_result.lineup_value_change):.1f} ROS pts."
    else:
        verdict = "Counter"
        reason = "This trade is roughly neutral for your lineup -- worth pushing for a bit more."

    return TradeEvaluation(my_result=my_result, their_result=their_result, verdict=verdict, reason=reason)
