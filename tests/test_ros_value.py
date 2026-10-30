"""Offline integration smoke tests for the shared ROS-value pipeline,
against the bundled demo=True snapshot -- no mocks needed. Unit tests on
each underlying piece (core/waiver.py, core/projection.py, data/stats.py)
already prove the math; this proves the wiring between them doesn't blow up
on real-shaped data and produces sane output.
"""

from data.demo import DEMO_LEAGUE_ID, DemoSleeperClient
from data.ros_value import load_ros_context, player_ros_value
from data.trade import build_trade_evaluation
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

    evaluation, breakdowns = build_trade_evaluation(
        league, my_roster, their_roster, players, gives, receives, league.season, 7, demo=True
    )

    assert evaluation.verdict in {"Accept", "Decline", "Counter"}
    assert set(breakdowns) == set(gives) | set(receives)
    for breakdown in breakdowns.values():
        assert breakdown.total >= 0.0


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
