"""Replays past weeks using only data available before each week, and
reports mean absolute error (MAE) by position against two naive baselines.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Callable


@dataclass
class PlayerSeries:
    position: str
    weekly_points: list[float]  # chronological, index 0 == week 1
    player_id: str | None = None  # lets predict_fn look up player-specific context


@dataclass
class BacktestResult:
    weeks_tested: list[int]
    model_mae_by_position: dict[str, float]
    season_avg_mae_by_position: dict[str, float]
    last_week_mae_by_position: dict[str, float]


def backtest(
    players: list[PlayerSeries],
    start_week: int,
    end_week: int,
    predict_fn: Callable[[list[float], PlayerSeries], float],
) -> BacktestResult:
    """For each player and each week in [start_week, end_week], predicts that
    week from `predict_fn(prior_weeks, player)` where `prior_weeks` is sliced
    to strictly exclude the replayed week and everything after it --
    appending data for later weeks can never change an earlier week's
    prediction. `player` is passed through so predict_fn can look up
    player-specific context (e.g. opponent/opportunity history) by
    `player.player_id`; predict_fn must never use `player.weekly_points`
    beyond what's already in `prior_weeks`.
    """
    model_errors: dict[str, list[float]] = {}
    season_avg_errors: dict[str, list[float]] = {}
    last_week_errors: dict[str, list[float]] = {}
    weeks_tested: set[int] = set()

    for player in players:
        for week in range(start_week, end_week + 1):
            if week > len(player.weekly_points):
                continue
            prior = player.weekly_points[: week - 1]
            if not prior:
                continue
            actual = player.weekly_points[week - 1]

            model_pred = predict_fn(prior, player)
            season_avg_pred = mean(prior)
            last_week_pred = prior[-1]

            pos = player.position
            model_errors.setdefault(pos, []).append(abs(model_pred - actual))
            season_avg_errors.setdefault(pos, []).append(abs(season_avg_pred - actual))
            last_week_errors.setdefault(pos, []).append(abs(last_week_pred - actual))
            weeks_tested.add(week)

    def _mae(errors: dict[str, list[float]]) -> dict[str, float]:
        return {pos: round(mean(vals), 2) for pos, vals in errors.items()}

    return BacktestResult(
        weeks_tested=sorted(weeks_tested),
        model_mae_by_position=_mae(model_errors),
        season_avg_mae_by_position=_mae(season_avg_errors),
        last_week_mae_by_position=_mae(last_week_errors),
    )
