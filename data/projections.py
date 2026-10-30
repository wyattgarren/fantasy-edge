"""Builds live current-week Projections for a roster, combining Sleeper
(roster, player status) with nflreadpy (data/stats.py) and the Phase 2
projection model (core/projection.py). Skill positions only (QB/RB/WR/TE) --
see data/stats.py's STAT_KEY_MAP note on K/DEF scope.
"""

from __future__ import annotations

from statistics import mean

import data.stats as stats
from core.projection import Projection, project_player
from data.models import League, Player, Roster

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}


def project_roster_week(
    league: League,
    roster: Roster,
    players: dict[str, Player],
    season: str,
    week: int,
    demo: bool = False,
) -> dict[str, Projection]:
    scoring_settings = league.scoring_settings

    weekly_stats = stats.load_weekly_stats(season, demo=demo)
    weekly_points = stats.weekly_fantasy_points(weekly_stats, scoring_settings)
    points_allowed = stats.points_allowed_by_position(weekly_points)
    snap_counts = stats.load_snap_counts(season, demo=demo)
    id_map = stats.load_player_id_map(demo=demo)
    opportunity = stats.opportunity_shares(weekly_stats, snap_counts, id_map)
    schedules = stats.load_schedules(season, demo=demo)

    projections: dict[str, Projection] = {}

    for player_id in roster.players:
        player = players.get(player_id)
        if player is None or player.position not in SKILL_POSITIONS or player.team is None:
            continue

        team = player.team
        prior_rows = weekly_points.filter(
            (weekly_points["player_id"] == _gsis_id(id_map, player_id))
            & (weekly_points["week"] < week)
        ).sort("week")
        weekly_points_list = prior_rows["fantasy_points"].to_list()
        weeks_played = len(weekly_points_list)

        opp_rows = opportunity.filter(
            (opportunity["sleeper_id"] == player_id) & (opportunity["week"] < week)
        ).sort("week")
        share_by_week = dict(
            zip(opp_rows["week"].to_list(), opp_rows["opportunity_share"].to_list())
        )
        prior_weeks = sorted(share_by_week)
        recent_weeks = prior_weeks[-3:]
        recent_share = mean(share_by_week[w] for w in recent_weeks) if recent_weeks else 0.0
        season_share = mean(share_by_week[w] for w in prior_weeks) if prior_weeks else 0.0

        is_bye = stats.is_bye_week(schedules, team, week)
        opponent = opponent_this_week(schedules, team, week)
        opp_allowed = (
            stats.points_allowed_through_week(points_allowed, opponent, player.position, week)
            if opponent
            else None
        )
        league_avg = stats.league_avg_points_allowed_through_week(
            points_allowed, player.position, week
        )
        if opp_allowed is None or league_avg is None:
            opp_allowed = league_avg = 0.0

        projections[player_id] = project_player(
            weekly_points=weekly_points_list,
            recent_share=recent_share,
            season_share=season_share,
            opponent_points_allowed=opp_allowed,
            league_avg_points_allowed=league_avg,
            weeks_played=weeks_played,
            status=player.injury_status,
            is_bye=is_bye,
        )

    return projections


def _gsis_id(id_map, sleeper_id: str) -> str | None:
    row = id_map.filter(id_map["sleeper_id"] == sleeper_id)
    if row.height == 0:
        return None
    return row["gsis_id"][0]


def opponent_this_week(schedules, team: str, week: int) -> str | None:
    games = schedules.filter(
        (schedules["week"] == week)
        & ((schedules["home_team"] == team) | (schedules["away_team"] == team))
    )
    if games.height == 0:
        return None
    row = games.row(0, named=True)
    return row["away_team"] if row["home_team"] == team else row["home_team"]
