"""Builds a live Monte Carlo simulation of this week's actual matchup
(roster.starters on both sides), combining data/projections.py's live
Projections with core/simulate.py.
"""

from __future__ import annotations

from core.simulate import PlayerDistribution, SimulationResult, simulate_matchup
from data.models import League, Player, Roster
from data.projections import SKILL_POSITIONS, project_roster_week

DEFAULT_RUNS = 10000


def build_matchup_simulation(
    league: League,
    my_roster: Roster,
    opponent_roster: Roster,
    players: dict[str, Player],
    season: str,
    week: int,
    runs: int = DEFAULT_RUNS,
    seed: int | None = None,
) -> SimulationResult:
    my_projections = project_roster_week(league, my_roster, players, season, week)
    opponent_projections = project_roster_week(league, opponent_roster, players, season, week)

    def starter_distributions(roster: Roster, projections) -> list[PlayerDistribution]:
        distributions = []
        for player_id in roster.starters:
            player = players.get(player_id)
            if player is None or player.position not in SKILL_POSITIONS:
                continue  # K/DEF: not modeled, excluded from the simulation
            projection = projections.get(player_id)
            if projection is None:
                continue
            distributions.append(
                PlayerDistribution(player_id=player_id, mean=projection.mean, std=projection.std)
            )
        return distributions

    my_distributions = starter_distributions(my_roster, my_projections)
    opponent_distributions = starter_distributions(opponent_roster, opponent_projections)

    return simulate_matchup(my_distributions, opponent_distributions, runs=runs, seed=seed)
