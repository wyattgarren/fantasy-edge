from core.waiver import (
    bid_percent_range,
    need_score,
    ros_value,
    suggest_drop,
    trending_bonus,
)


def test_ros_value_no_opportunity_trend():
    # baseline([10,20,30,40]) = 0.5*mean([20,30,40]) + 0.5*mean(all) = 0.5*30+0.5*25 = 27.5
    assert ros_value([10, 20, 30, 40], recent_share=0.25, season_share=0.25, remaining_weeks=5) == 137.5


def test_ros_value_with_rising_opportunity():
    # baseline([10,10,10]) = 10; ratio 0.3/0.2=1.5 clamped to 1.3 -> opp_adj = 10*0.3 = 3
    # per_game_raw = 13, shrunk by 3/4 games of history -> 9.75, remaining_weeks=4
    assert ros_value([10, 10, 10], recent_share=0.3, season_share=0.2, remaining_weeks=4) == 39.0


def test_ros_value_zero_remaining_weeks():
    assert ros_value([10, 10, 10], recent_share=0.3, season_share=0.2, remaining_weeks=0) == 0.0


def test_ros_value_no_history():
    assert ros_value([], recent_share=0.2, season_share=0.2, remaining_weeks=5) == 0.0


def test_ros_value_shrinks_a_single_fluke_game():
    # one 20-point game is NOT the same as a proven 20-point-per-game player:
    # shrunk by 1/4 games of history -> per_game = 20*0.25 = 5.0
    value = ros_value([20.0], recent_share=0.3, season_share=0.3, remaining_weeks=7)
    assert value == 35.0
    naive_unshrunk = 20.0 * 7  # what it would be with no sample-size regularization
    assert value < naive_unshrunk


def test_ros_value_no_shrinkage_once_past_the_threshold():
    # 4 games (at the shrinkage_full_weeks default) and 8 games should give
    # the same per-game trust -- shrinkage caps at 1.0, it isn't an ongoing
    # bonus for a longer track record.
    four_games = ros_value([10.0] * 4, recent_share=0.3, season_share=0.3, remaining_weeks=5)
    eight_games = ros_value([10.0] * 8, recent_share=0.3, season_share=0.3, remaining_weeks=5)
    assert four_games == eight_games == 50.0


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
