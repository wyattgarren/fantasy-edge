from core.waiver import (
    bid_percent_range,
    need_score,
    position_age_multiplier,
    replacement_ranks,
    ros_value,
    suggest_drop,
    trending_bonus,
)


def test_ros_value_no_opportunity_trend():
    # baseline([10,20,30,40]) = 0.5*mean([20,30,40]) + 0.5*mean(all) = 0.5*30+0.5*25 = 27.5
    result = ros_value(
        [10, 20, 30, 40], recent_share=0.25, season_share=0.25, week_weights=[1.0] * 5
    )
    assert result.total == 137.5


def test_ros_value_with_rising_opportunity():
    # baseline([10,10,10]) = 10; ratio 0.3/0.2=1.5 clamped to 1.3 -> opp_adj = 10*0.3 = 3
    # per_game_raw = 13, shrunk by 3/4 games of history -> 9.75, 4 weeks
    result = ros_value([10, 10, 10], recent_share=0.3, season_share=0.2, week_weights=[1.0] * 4)
    assert result.total == 39.0


def test_ros_value_zero_remaining_weeks():
    result = ros_value([10, 10, 10], recent_share=0.3, season_share=0.2, week_weights=[])
    assert result.total == 0.0


def test_ros_value_no_history():
    result = ros_value([], recent_share=0.2, season_share=0.2, week_weights=[1.0] * 5)
    assert result.total == 0.0


def test_ros_value_shrinks_a_single_fluke_game():
    # one 20-point game is NOT the same as a proven 20-point-per-game player:
    # shrunk by 1/4 games of history -> per_game = 20*0.25 = 5.0
    result = ros_value([20.0], recent_share=0.3, season_share=0.3, week_weights=[1.0] * 7)
    assert result.total == 35.0
    naive_unshrunk = 20.0 * 7  # what it would be with no sample-size regularization
    assert result.total < naive_unshrunk


def test_ros_value_no_shrinkage_once_past_the_threshold():
    # 4 games (at the shrinkage_full_weeks default) and 8 games should give
    # the same per-game trust -- shrinkage caps at 1.0, it isn't an ongoing
    # bonus for a longer track record.
    four_games = ros_value([10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0] * 5)
    eight_games = ros_value([10.0] * 8, recent_share=0.3, season_share=0.3, week_weights=[1.0] * 5)
    assert four_games.total == eight_games.total == 50.0


def test_ros_value_bye_week_zeroes_that_weeks_contribution():
    no_bye = ros_value([10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0] * 5)
    with_bye = ros_value(
        [10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0, 0.0, 1.0, 1.0, 1.0]
    )
    assert with_bye.games_weight == no_bye.games_weight - 1
    assert with_bye.total < no_bye.total


def test_ros_value_playoff_week_weight_increases_total():
    regular = ros_value([10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0] * 5)
    with_playoff_week = ros_value(
        [10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0, 1.0, 1.0, 1.0, 1.5]
    )
    assert with_playoff_week.total > regular.total


def test_ros_value_availability_multiplier_affects_only_first_week():
    full_health = ros_value([10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0] * 3)
    out_this_week = ros_value(
        [10.0] * 4,
        recent_share=0.3,
        season_share=0.3,
        week_weights=[1.0] * 3,
        availability_multiplier=0.0,
    )
    # only week_weights[0]'s contribution (1 game) is zeroed, not all 3
    assert out_this_week.games_weight == full_health.games_weight - 1


def test_ros_value_regression_shifts_per_game():
    baseline_only = ros_value([10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0])
    with_regression = ros_value(
        [10.0] * 4,
        recent_share=0.3,
        season_share=0.3,
        week_weights=[1.0],
        regression_points_per_game=-2.0,
    )
    assert with_regression.per_game == baseline_only.per_game - 2.0


def test_ros_value_age_multiplier_scales_per_game():
    full = ros_value([10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0])
    aged = ros_value(
        [10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0], age_multiplier=0.8
    )
    assert aged.per_game == full.per_game * 0.8


def test_ros_value_per_game_floors_at_zero():
    result = ros_value(
        [1.0] * 4,
        recent_share=0.3,
        season_share=0.3,
        week_weights=[1.0],
        regression_points_per_game=-100.0,
    )
    assert result.per_game == 0.0
    assert result.total == 0.0


def test_ros_value_game_script_shifts_per_game():
    baseline_only = ros_value([10.0] * 4, recent_share=0.3, season_share=0.3, week_weights=[1.0])
    with_game_script = ros_value(
        [10.0] * 4,
        recent_share=0.3,
        season_share=0.3,
        week_weights=[1.0],
        avg_game_script_adjustment=0.4,
    )
    assert with_game_script.per_game == baseline_only.per_game + 0.4


def test_replacement_ranks_no_flex():
    # 10-team league, 1 QB/2 RB/2 WR/1 TE, no FLEX/SUPER_FLEX
    roster_positions = ["QB", "RB", "RB", "WR", "WR", "TE", "BN", "BN"]
    ranks = replacement_ranks(roster_positions, team_count=10)
    assert ranks == {"QB": 10, "RB": 20, "WR": 20, "TE": 10}


def test_replacement_ranks_splits_flex_evenly():
    # 1 FLEX (RB/WR/TE eligible) across 10 teams = 10 extra slots / 3 positions
    roster_positions = ["QB", "RB", "WR", "TE", "FLEX"]
    ranks = replacement_ranks(roster_positions, team_count=10)
    extra = 10 / 3
    assert ranks["QB"] == 10
    assert ranks["RB"] == round(10 + extra)
    assert ranks["WR"] == round(10 + extra)
    assert ranks["TE"] == round(10 + extra)


def test_replacement_ranks_splits_super_flex_evenly():
    roster_positions = ["QB", "RB", "WR", "TE", "SUPER_FLEX"]
    ranks = replacement_ranks(roster_positions, team_count=10)
    extra = 10 / 4
    assert ranks["QB"] == round(10 + extra)
    assert ranks["RB"] == round(10 + extra)
    assert ranks["WR"] == round(10 + extra)
    assert ranks["TE"] == round(10 + extra)


def test_replacement_ranks_scales_with_team_count():
    roster_positions = ["QB", "RB", "RB", "WR", "WR", "TE"]
    small = replacement_ranks(roster_positions, team_count=8)
    large = replacement_ranks(roster_positions, team_count=14)
    for position in small:
        assert large[position] > small[position]


def test_position_age_multiplier_rb_at_or_below_peak():
    assert position_age_multiplier("RB", 25) == 1.0
    assert position_age_multiplier("RB", 27) == 1.0


def test_position_age_multiplier_rb_past_peak():
    assert round(position_age_multiplier("RB", 30), 2) == 0.76


def test_position_age_multiplier_floors():
    assert position_age_multiplier("RB", 60) == 0.60


def test_position_age_multiplier_wr_te_qb_spot_checks():
    assert position_age_multiplier("WR", 29) == 1.0
    assert position_age_multiplier("WR", 34) < 1.0
    assert position_age_multiplier("TE", 32) == 1.0
    assert round(position_age_multiplier("TE", 34), 2) == 0.89
    assert position_age_multiplier("QB", 34) == 1.0
    assert position_age_multiplier("QB", 38) < 1.0


def test_position_age_multiplier_unknown_position_or_age():
    assert position_age_multiplier("K", 30) == 1.0
    assert position_age_multiplier("RB", None) == 1.0


def test_need_score_deficit_only():
    result = need_score(required_starters=2, healthy_count=1, upcoming_byes=0)
    assert result.deficit == 1
    assert result.upcoming_byes == 0
    assert result.score == 10.0


def test_need_score_surplus_has_no_deficit():
    result = need_score(required_starters=2, healthy_count=3, upcoming_byes=0)
    assert result.deficit == 0
    assert result.score == 0.0


def test_need_score_upcoming_byes_only():
    result = need_score(required_starters=2, healthy_count=2, upcoming_byes=2)
    assert result.deficit == 0
    assert result.score == 4.0


def test_need_score_combines_deficit_and_byes():
    result = need_score(required_starters=3, healthy_count=1, upcoming_byes=1)
    assert result.deficit == 2
    assert result.score == 22.0


def test_trending_bonus_tiers():
    assert trending_bonus(1) == 3.0
    assert trending_bonus(10) == 3.0
    assert trending_bonus(11) == 1.5
    assert trending_bonus(25) == 1.5
    assert trending_bonus(26) == 0.5
    assert trending_bonus(None) == 0.0


def test_suggest_drop_picks_lowest_value_among_surplus_positions():
    roster_positions = ["RB", "RB", "WR"]
    candidates = [
        ("rb1", "RB", 10.0),
        ("rb2", "RB", 5.0),
        ("rb3", "RB", 8.0),  # RB has 3 rostered vs 2 slots -> surplus
        ("wr1", "WR", 12.0),  # WR has 1 rostered vs 1 slot -> not surplus
    ]
    assert suggest_drop(candidates, roster_positions) == "rb2"


def test_suggest_drop_returns_none_with_no_surplus():
    roster_positions = ["RB", "RB", "WR"]
    candidates = [("rb1", "RB", 10.0), ("rb2", "RB", 5.0), ("wr1", "WR", 12.0)]
    assert suggest_drop(candidates, roster_positions) is None


def test_bid_percent_range_known_values():
    low, high = bid_percent_range(value_percentile=0.5, teams_needing=0, total_teams=10)
    assert round(low, 2) == 9.2
    assert round(high, 2) == 13.8


def test_bid_percent_range_increases_with_value_percentile():
    low_a, high_a = bid_percent_range(0.0, teams_needing=0, total_teams=10)
    low_b, high_b = bid_percent_range(1.0, teams_needing=0, total_teams=10)
    assert low_b > low_a
    assert high_b > high_a


def test_bid_percent_range_increases_with_competition():
    low_a, high_a = bid_percent_range(0.5, teams_needing=0, total_teams=10)
    low_b, high_b = bid_percent_range(0.5, teams_needing=10, total_teams=10)
    assert low_b > low_a
    assert high_b > high_a


def test_bid_percent_range_stays_within_bounds():
    low, high = bid_percent_range(1.0, teams_needing=10, total_teams=10)
    assert 0.0 <= low <= 100.0
    assert 0.0 <= high <= 100.0
