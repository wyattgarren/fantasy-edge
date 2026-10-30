import polars as pl

from data.stats import (
    expected_points_diff_ratio,
    remaining_week_weights,
    remaining_weeks_and_matchup_adjustment,
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


def test_remaining_weeks_and_matchup_adjustment_excludes_byes_and_averages():
    schedules = pl.DataFrame(
        {
            "week": [1, 2, 3],
            "home_team": ["AAA", "XXX", "CCC"],
            "away_team": ["BBB", "YYY", "AAA"],
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
    # average of [+5, -5] = 0.0
    weeks, avg_adjustment = remaining_weeks_and_matchup_adjustment(
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
    assert avg_adjustment == 0.0
