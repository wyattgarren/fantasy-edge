"""Ranks real free agents for the waiver wire, combining Sleeper (rosters,
trending adds) with nflreadpy (data/stats.py) and core/waiver.py's
transparent scoring. Skill positions only (QB/RB/WR/TE).
"""

from __future__ import annotations

import data.stats as stats
from core.waiver import (
    NeedBreakdown,
    WaiverTarget,
    bid_percent_range,
    need_score,
    suggest_drop,
    trending_bonus,
)
from data.models import League, Player, Roster
from data.ros_value import load_ros_context, player_ros_value
from data.sleeper import SleeperClient

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}
UPCOMING_BYE_WINDOW = 3


def free_agents(
    players: dict[str, Player],
    rostered_ids: set[str],
    played_gsis_ids: set[str],
    sleeper_to_gsis: dict[str, str | None],
) -> list[str]:
    """Active skill-position players not on any roster in the league, with
    at least one real stat-line recorded this season (the pool of ~12k
    Sleeper players is otherwise far too large/irrelevant to rank)."""
    return [
        pid
        for pid, p in players.items()
        if pid not in rostered_ids
        and p.status == "Active"
        and p.position in SKILL_POSITIONS
        and sleeper_to_gsis.get(pid) in played_gsis_ids
    ]


def _upcoming_byes(schedules, team: str, week: int, window: int) -> int:
    return sum(1 for w in range(week, week + window) if stats.is_bye_week(schedules, team, w))


def roster_need_by_position(
    player_ids: list[str],
    players: dict[str, Player],
    roster_ros: dict[str, float],
    roster_positions: list[str],
    schedules,
    week: int,
) -> dict[str, NeedBreakdown]:
    """`player_ids` is any list of rostered-skill-position player ids --
    a real roster's `.players`, or a hypothetical post-trade player set
    (see data/trade.py's handcuff-risk check), not necessarily a real
    Roster object."""
    required_by_position: dict[str, int] = {}
    for pos in roster_positions:
        if pos in SKILL_POSITIONS:
            required_by_position[pos] = required_by_position.get(pos, 0) + 1

    healthy_by_position = dict.fromkeys(required_by_position, 0)
    byes_by_position = dict.fromkeys(required_by_position, 0)
    for pid in player_ids:
        player = players.get(pid)
        if player is None or player.position not in required_by_position:
            continue
        if roster_ros.get(pid, 0.0) > 0:
            healthy_by_position[player.position] += 1
        if player.team and _upcoming_byes(schedules, player.team, week, UPCOMING_BYE_WINDOW) > 0:
            byes_by_position[player.position] += 1

    return {
        pos: need_score(required_by_position[pos], healthy_by_position[pos], byes_by_position[pos])
        for pos in required_by_position
    }


def build_waiver_board(
    client: SleeperClient,
    league: League,
    rosters: list[Roster],
    my_roster: Roster,
    players: dict[str, Player],
    season: str,
    week: int,
    demo: bool = False,
) -> tuple[list[WaiverTarget], int]:
    """Returns (waiver targets sorted by score descending, total relevant
    free-agent pool size)."""
    is_faab = float(league.settings.get("waiver_budget") or 0) > 0

    ctx = load_ros_context(league, season, week, demo=demo)
    schedules = ctx.schedules
    played_gsis_ids = set(ctx.weekly_points["player_id"].unique().to_list())

    rostered_ids = {pid for r in rosters for pid in r.players}
    candidate_ids = free_agents(players, rostered_ids, played_gsis_ids, ctx.sleeper_to_gsis)

    trending = client.get_trending(type="add", lookback_hours=24, limit=100)
    trending_rank = {t.player_id: i + 1 for i, t in enumerate(trending)}

    def roster_ros_values(roster: Roster) -> dict[str, float]:
        return {
            pid: player_ros_value(ctx, players[pid], pid).total
            for pid in roster.players
            if players.get(pid) is not None and players[pid].position in SKILL_POSITIONS
        }

    free_agent_ros = {pid: player_ros_value(ctx, players[pid], pid).total for pid in candidate_ids}
    my_roster_ros = roster_ros_values(my_roster)
    my_need = roster_need_by_position(
        my_roster.players, players, my_roster_ros, league.roster_positions, schedules, week
    )

    # how many OTHER teams show need at each position -> FAAB competition factor
    other_rosters_need: dict[str, int] = dict.fromkeys(my_need, 0)
    for roster in rosters:
        if roster.roster_id == my_roster.roster_id:
            continue
        need = roster_need_by_position(
            roster.players, players, roster_ros_values(roster), league.roster_positions, schedules, week
        )
        for pos, breakdown in need.items():
            if breakdown.score > 0:
                other_rosters_need[pos] = other_rosters_need.get(pos, 0) + 1

    total_other_teams = max(len(rosters) - 1, 1)

    drop_candidates = [(pid, players[pid].position, value) for pid, value in my_roster_ros.items()]
    suggested_drop = suggest_drop(drop_candidates, league.roster_positions)

    ranked = sorted(free_agent_ros.items(), key=lambda kv: kv[1], reverse=True)
    pool_size = len(ranked)
    max_value = ranked[0][1] if ranked else 0.0

    targets: list[WaiverTarget] = []
    for pid, value in ranked:
        position = players[pid].position
        need = my_need.get(position)
        need_bonus = need.score if need else 0.0
        trend_bonus = trending_bonus(trending_rank.get(pid))
        score = value + need_bonus + trend_bonus

        bid_low = bid_high = None
        if is_faab and max_value > 0:
            # value-based, not rank-based: with hundreds of mostly-irrelevant
            # free agents, a rank-based percentile crams every real target
            # near the 100th percentile and barely differentiates them
            percentile = value / max_value
            teams_needing = other_rosters_need.get(position, 0)
            bid_low, bid_high = bid_percent_range(percentile, teams_needing, total_other_teams)

        targets.append(
            WaiverTarget(
                player_id=pid,
                ros_value=value,
                need_bonus=need_bonus,
                trending_bonus=trend_bonus,
                score=score,
                suggested_drop_player_id=suggested_drop,
                bid_low=bid_low,
                bid_high=bid_high,
            )
        )

    targets.sort(key=lambda t: t.score, reverse=True)
    return targets, pool_size
