"""Offline integration smoke tests for the shared ROS-value pipeline,
against the bundled demo=True snapshot -- no mocks needed. Unit tests on
each underlying piece (core/waiver.py, core/projection.py, data/stats.py)
already prove the math; this proves the wiring between them doesn't blow up
on real-shaped data and produces sane output.
"""

import polars as pl

from data.demo import DEMO_LEAGUE_ID, DemoSleeperClient
from data.models import Player
from data.ros_value import compute_vorp, load_ros_context, player_ros_value
from data.trade import _handcuff_warnings, build_trade_evaluation
from data.waiver import build_waiver_board


def _demo_league_and_rosters():
    client = DemoSleeperClient()
    league = client.get_league(DEMO_LEAGUE_ID)
    rosters = client.get_rosters(DEMO_LEAGUE_ID)
    players = client.get_players()
    return client, league, rosters, players


def test_player_ros_value_against_demo_data_is_sane():
    client, league, rosters, players = _demo_league_and_rosters()
    ctx = load_ros_context(league, league.season, week=7, demo=True)

    my_roster = next(r for r in rosters if r.players)
    skill_player_ids = [
        pid
        for pid in my_roster.players
        if players.get(pid) is not None and players[pid].position in {"QB", "RB", "WR", "TE"}
    ]
    assert skill_player_ids

    for player_id in skill_player_ids:
        breakdown = player_ros_value(ctx, players[player_id], player_id)
        assert breakdown.total >= 0.0
        assert breakdown.games_weight >= 0.0
        assert 0.0 <= breakdown.age_multiplier <= 1.0
        assert 0.0 <= breakdown.availability_multiplier <= 1.0


def test_build_trade_evaluation_against_demo_data_runs_end_to_end():
    client, league, rosters, players = _demo_league_and_rosters()
    my_roster, their_roster = rosters[0], rosters[1]

    def skill_players(roster):
        return [
            pid
            for pid in roster.players
            if players.get(pid) is not None and players[pid].position in {"QB", "RB", "WR", "TE"}
        ]

    gives = skill_players(my_roster)[:1]
    receives = skill_players(their_roster)[:1]
    assert gives and receives

    evaluation, breakdowns, vorp, handcuff_warnings = build_trade_evaluation(
        league, rosters, my_roster, their_roster, players, gives, receives, league.season, 7, demo=True
    )

    assert evaluation.verdict in {"Accept", "Decline", "Counter"}
    assert set(breakdowns) == set(gives) | set(receives)
    for breakdown in breakdowns.values():
        assert breakdown.total >= 0.0

    assert set(vorp) == set(gives) | set(receives)
    for value in vorp.values():
        assert isinstance(value, float)

    assert set(handcuff_warnings) == {"you", "them"}
    for warnings in handcuff_warnings.values():
        assert isinstance(warnings, list)
        assert all(isinstance(w, str) for w in warnings)


def test_handcuff_warnings_fires_when_trade_creates_a_deficit():
    roster_positions = ["RB", "RB", "WR", "WR", "TE"]
    players = {
        "rb1": Player(player_id="rb1", position="RB", team=None),
        "rb2": Player(player_id="rb2", position="RB", team=None),
        "wr1": Player(player_id="wr1", position="WR", team=None),
        "wr2": Player(player_id="wr2", position="WR", team=None),
        "te1": Player(player_id="te1", position="TE", team=None),
    }
    pre_trade_ros = {"rb1": 10.0, "rb2": 8.0, "wr1": 5.0, "wr2": 4.0, "te1": 3.0}
    # trading away rb2 drops healthy RB count from 2 (meets the 2 required) to 1
    post_trade_ros = {"rb1": 10.0, "wr1": 5.0, "wr2": 4.0, "te1": 3.0}
    schedules = pl.DataFrame({"week": [], "home_team": [], "away_team": []})

    warnings = _handcuff_warnings(roster_positions, players, pre_trade_ros, post_trade_ros, schedules, week=1)
    assert len(warnings) == 1
    assert "RB" in warnings[0]


def test_handcuff_warnings_silent_when_depth_stays_fine():
    roster_positions = ["RB", "RB", "WR", "WR", "TE"]
    players = {
        "rb1": Player(player_id="rb1", position="RB", team=None),
        "rb2": Player(player_id="rb2", position="RB", team=None),
        "rb3": Player(player_id="rb3", position="RB", team=None),
        "wr1": Player(player_id="wr1", position="WR", team=None),
        "wr2": Player(player_id="wr2", position="WR", team=None),
        "te1": Player(player_id="te1", position="TE", team=None),
    }
    pre_trade_ros = {"rb1": 10.0, "rb2": 8.0, "rb3": 6.0, "wr1": 5.0, "wr2": 4.0, "te1": 3.0}
    # trading away the 3rd-string RB leaves 2 healthy RBs -- still meets the 2 required
    post_trade_ros = {"rb1": 10.0, "rb2": 8.0, "wr1": 5.0, "wr2": 4.0, "te1": 3.0}
    schedules = pl.DataFrame({"week": [], "home_team": [], "away_team": []})

    warnings = _handcuff_warnings(roster_positions, players, pre_trade_ros, post_trade_ros, schedules, week=1)
    assert warnings == []


def test_compute_vorp_against_demo_data_ranks_the_top_player_positive():
    client, league, rosters, players = _demo_league_and_rosters()
    ctx = load_ros_context(league, league.season, week=7, demo=True)

    vorp_by_player = compute_vorp(ctx, rosters, players, league.roster_positions)
    assert vorp_by_player

    # the single highest-ros_value RB in the league should show positive
    # VORP (clearly above replacement level by definition, unless every
    # rostered RB in the league is below the computed replacement rank).
    rb_ids = [
        pid
        for roster in rosters
        for pid in roster.players
        if players.get(pid) is not None and players[pid].position == "RB"
    ]
    assert rb_ids
    best_rb = max(rb_ids, key=lambda pid: player_ros_value(ctx, players[pid], pid).total)
    assert vorp_by_player[best_rb] >= 0.0


def test_build_waiver_board_against_demo_data_runs_end_to_end():
    client, league, rosters, players = _demo_league_and_rosters()
    my_roster = rosters[0]

    targets, pool_size = build_waiver_board(
        client, league, rosters, my_roster, players, league.season, 7, demo=True
    )

    assert pool_size > 0
    assert targets
    assert all(t.ros_value >= 0.0 for t in targets)
    # sorted by score descending
    assert all(targets[i].score >= targets[i + 1].score for i in range(len(targets) - 1))
