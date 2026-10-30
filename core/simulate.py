"""Monte Carlo simulation of a matchup: win probability, projected score
range, and which players swing the result most. Pure math, no I/O.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from statistics import mean


@dataclass
class PlayerDistribution:
    player_id: str
    mean: float
    std: float


@dataclass
class SimulationResult:
    win_probability: float
    my_mean: float
    my_floor: float
    my_ceiling: float
    opponent_mean: float
    swing_players: list[tuple[str, float]] = field(default_factory=list)
    runs: int = 0


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, round(pct * (len(sorted_values) - 1))))
    return sorted_values[idx]


def simulate_matchup(
    my_players: list[PlayerDistribution],
    opponent_players: list[PlayerDistribution],
    runs: int = 10000,
    seed: int | None = None,
) -> SimulationResult:
    rng = random.Random(seed)

    my_totals: list[float] = []
    opp_totals: list[float] = []
    my_draws_by_player: dict[str, list[float]] = {p.player_id: [] for p in my_players}
    wins = 0.0

    for _ in range(runs):
        my_run_draws = {p.player_id: max(0.0, rng.gauss(p.mean, p.std)) for p in my_players}
        my_total = sum(my_run_draws.values())
        opp_total = sum(max(0.0, rng.gauss(p.mean, p.std)) for p in opponent_players)

        my_totals.append(my_total)
        opp_totals.append(opp_total)
        for pid, draw in my_run_draws.items():
            my_draws_by_player[pid].append(draw)

        if my_total > opp_total:
            wins += 1.0
        elif my_total == opp_total:
            wins += 0.5

    win_probability = wins / runs if runs else 0.0
    win_mask = [my_totals[i] > opp_totals[i] for i in range(runs)]

    swings: list[tuple[str, float]] = []
    for pid, draws in my_draws_by_player.items():
        win_draws = [d for d, w in zip(draws, win_mask) if w]
        loss_draws = [d for d, w in zip(draws, win_mask) if not w]
        swing = (mean(win_draws) if win_draws else 0.0) - (mean(loss_draws) if loss_draws else 0.0)
        swings.append((pid, swing))
    swings.sort(key=lambda item: abs(item[1]), reverse=True)

    sorted_my = sorted(my_totals)

    return SimulationResult(
        win_probability=win_probability,
        my_mean=mean(my_totals) if my_totals else 0.0,
        my_floor=_percentile(sorted_my, 0.2),
        my_ceiling=_percentile(sorted_my, 0.8),
        opponent_mean=mean(opp_totals) if opp_totals else 0.0,
        swing_players=swings,
        runs=runs,
    )
