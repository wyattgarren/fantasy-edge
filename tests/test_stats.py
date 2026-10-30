import polars as pl

from data.stats import (
    expected_points_diff_ratio,
    remaining_week_weights,
    remaining_weeks_and_schedule_adjustments,
    team_spread_and_total,
)


def test_expected_points_diff_ratio_known_value():
    expected_points = pl.DataFrame(
        {
            "player_id": ["p1", "p1"],
            "week": [1, 2],
            "total_fantasy_points": [12.0, 18.0],
            "total_fantasy_points_exp": [10.0, 10.0],
        }
    )
    # actual_total=30, expected_total=20 -> (30-20)/20 = 0.5
    assert expected_points_diff_ratio(expected_points, "p1", before_week=3) == 0.5


def test_expected_points_diff_ratio_none_when_no_prior_rows():
    expected_points = pl.DataFrame(
        {
            "player_id": ["p1"],
            "week": [5],
            "total_fantasy_points": [12.0],
            "total_fantasy_points_exp": [10.0],
        }
    )
    assert expected_points_diff_ratio(expected_points, "p1", before_week=3) is None
    assert expected_points_diff_ratio(expected_points, "unknown", before_week=10) is None


def test_expected_points_diff_ratio_none_when_expected_sums_to_zero():
    expected_points = pl.DataFrame(
        {
            "player_id": ["p1"],
            "week": [1],
            "total_fantasy_points": [5.0],
            "total_fantasy_points_exp": [0.0],
        }
    )
    assert expected_points_diff_ratio(expected_points, "p1", before_week=2) is None


def test_remaining_week_weights_bye_playoff_and_normal():
    schedules = pl.DataFrame(
        {
            "week": [1, 2, 4],
            "home_team": ["AAA", "XXX", "AAA"],
            "away_team": ["BBB", "YYY", "ZZZ"],
        }
    )
    # AAA plays weeks 1 and 4, has no game at week 2 or 3 (bye); week 4 is playoff
    weights = remaining_week_weights(
        schedules, "AAA", from_week=1, to_week=4, playoff_week_start=4, playoff_week_weight=2.0
    )
    assert weights == [1.0, 0.0, 0.0, 2.0]


def test_remaining_week_weights_defaults_to_core_waiver_constant():
    from core.waiver import PLAYOFF_WEEK_WEIGHT

    schedules = pl.DataFrame({"week": [1], "home_team": ["AAA"], "away_team": ["BBB"]})
    weights = remaining_week_weights(schedules, "AAA", from_week=1, to_week=1, playoff_week_start=1)
    assert weights == [PLAYOFF_WEEK_WEIGHT]


def test_team_spread_and_total_home_and_away_sign():
    schedules = pl.DataFrame(
        {
            "week": [1, 2],
            "home_team": ["AAA", "XXX"],
            "away_team": ["BBB", "AAA"],
            "spread_line": [3.0, -4.0],
            "total_line": [45.0, 50.0],
        }
    )
    # AAA is home in week 1 -> spread as-is (favored by 3)
    assert team_spread_and_total(schedules, "AAA", 1) == (3.0, 45.0)
    # AAA is away in week 2 -> sign flipped (home XXX favored by -4 means AAA favored by +4)
    assert team_spread_and_total(schedules, "AAA", 2) == (4.0, 50.0)


def test_team_spread_and_total_no_game_or_no_line():
    schedules = pl.DataFrame(
        {
            "week": [1, 2],
            "home_team": ["AAA", "AAA"],
            "away_team": ["BBB", "CCC"],
            "spread_line": [3.0, None],
            "total_line": [45.0, None],
        }
    )
    assert team_spread_and_total(schedules, "AAA", 3) == (None, None)  # no game that week
    assert team_spread_and_total(schedules, "AAA", 2) == (None, None)  # line not posted yet


def test_remaining_weeks_and_schedule_adjustments_excludes_byes_and_averages():
    schedules = pl.DataFrame(
        {
            "week": [1, 2, 3],
            "home_team": ["AAA", "XXX", "CCC"],
            "away_team": ["BBB", "YYY", "AAA"],
            "spread_line": [None, None, None],
            "total_line": [None, None, None],
        }
    )
    points_allowed = pl.DataFrame(
        {
            "opponent_team": ["BBB", "CCC"],
            "position": ["RB", "RB"],
            "week": [1, 1],
            "points_allowed": [20.0, 10.0],
        }
    )
    # league avg RB points allowed (both rows, week<4) = mean(20, 10) = 15
    # week 1 opponent BBB allowed 20 -> matchup_adjustment(20, 15, weeks_played=8) = +5
    # week 2 is AAA's bye -> excluded
    # week 3 opponent CCC allowed 10 -> matchup_adjustment(10, 15, weeks_played=8) = -5
    # average of [+5, -5] = 0.0; no Vegas lines posted -> game-script average is 0.0 too
    weeks, avg_matchup_adjustment, avg_game_script_adjustment = remaining_weeks_and_schedule_adjustments(
        schedules,
        points_allowed,
        team="AAA",
        position="RB",
        weeks_played=8,
        from_week=1,
        to_week=3,
        before_week=4,
    )
    assert weeks == [1, 3]
    assert avg_matchup_adjustment == 0.0
    assert avg_game_script_adjustment == 0.0


def test_remaining_weeks_and_schedule_adjustments_averages_game_script():
    schedules = pl.DataFrame(
        {
            "week": [1, 2],
            "home_team": ["AAA", "AAA"],
            "away_team": ["BBB", "CCC"],
            "spread_line": [10.0, 10.0],  # AAA favored by 10 both weeks (home)
            "total_line": [44.55, 44.55],  # exactly NEUTRAL_TOTAL -> total term is 0
        }
    )
    points_allowed = pl.DataFrame(
        {"opponent_team": [], "position": [], "week": [], "points_allowed": []},
        schema={"opponent_team": pl.Utf8, "position": pl.Utf8, "week": pl.Int64, "points_allowed": pl.Float64},
    )
    # RB, spread=10 both weeks -> game_script_adjustment = 0.0423*10 = 0.423 each week
    weeks, _, avg_game_script_adjustment = remaining_weeks_and_schedule_adjustments(
        schedules,
        points_allowed,
        team="AAA",
        position="RB",
        weeks_played=8,
        from_week=1,
        to_week=2,
        before_week=1,
    )
    assert weeks == [1, 2]
    assert round(avg_game_script_adjustment, 3) == 0.423
