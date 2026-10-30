from core.projection import (
    availability_multiplier,
    baseline_points,
    matchup_adjustment,
    opportunity_adjustment,
    project_player,
)


def test_baseline_points_blends_recent_and_season():
    # recent 3 avg = (20+30+40)/3 = 30, season avg = (10+20+30+40)/4 = 25
    # 0.5*30 + 0.5*25 = 27.5
    assert baseline_points([10, 20, 30, 40]) == 27.5


def test_baseline_points_empty_history():
    assert baseline_points([]) == 0.0


def test_opportunity_adjustment_rising_share():
    # ratio 0.3/0.2 = 1.5, clamped to max_ratio 1.3 -> 20*(1.3-1)
    assert round(opportunity_adjustment(0.3, 0.2, baseline=20), 4) == 6.0


def test_opportunity_adjustment_falling_share_is_clamped():
    # ratio 0.1/0.2 = 0.5, clamped to min_ratio 0.7 -> 20*(0.7-1)
    assert round(opportunity_adjustment(0.1, 0.2, baseline=20), 4) == -6.0


def test_opportunity_adjustment_no_clamp_needed():
    assert round(opportunity_adjustment(0.22, 0.2, baseline=20), 4) == 2.0


def test_opportunity_adjustment_zero_season_share():
    assert opportunity_adjustment(0.1, 0.0, baseline=20) == 0.0


def test_matchup_adjustment_full_shrinkage():
    assert matchup_adjustment(25, 20, weeks_played=8, shrinkage_full_weeks=8) == 5.0


def test_matchup_adjustment_partial_shrinkage():
    assert matchup_adjustment(25, 20, weeks_played=4, shrinkage_full_weeks=8) == 2.5


def test_matchup_adjustment_no_games_played_shrinks_to_zero():
    assert matchup_adjustment(25, 20, weeks_played=0, shrinkage_full_weeks=8) == 0.0


def test_availability_multiplier_active():
    assert availability_multiplier("Active") == 1.0
    assert availability_multiplier(None) == 1.0


def test_availability_multiplier_out_statuses():
    assert availability_multiplier("Out") == 0.0
    assert availability_multiplier("IR") == 0.0


def test_availability_multiplier_discounts():
    assert availability_multiplier("Doubtful") == 0.5
    assert availability_multiplier("Questionable") == 0.85


def test_availability_multiplier_bye_overrides_status():
    assert availability_multiplier("Active", is_bye=True) == 0.0


def test_project_player_known_values():
    projection = project_player(
        weekly_points=[10, 15, 20],
        recent_share=0.25,
        season_share=0.25,
        opponent_points_allowed=20,
        league_avg_points_allowed=20,
        weeks_played=8,
        status="Active",
    )
    assert projection.mean == 15.0
    assert projection.std == 5.0
    assert projection.floor == 10.79
    assert projection.ceiling == 19.21
    assert projection.components == {
        "baseline": 15.0,
        "opportunity_adjustment": 0.0,
        "matchup_adjustment": 0.0,
        "availability_multiplier": 1.0,
    }


def test_project_player_bye_week_zeroes_everything():
    projection = project_player(
        weekly_points=[10, 15, 20],
        recent_share=0.25,
        season_share=0.25,
        opponent_points_allowed=20,
        league_avg_points_allowed=20,
        weeks_played=8,
        status="Active",
        is_bye=True,
    )
    assert projection.mean == 0.0
    assert projection.floor == 0.0
    assert projection.ceiling == 0.0
    assert projection.std == 0.0
    # components still show what the projection would have been, for the UI
    assert projection.components["baseline"] == 15.0
    assert projection.components["availability_multiplier"] == 0.0


def test_project_player_out_status_zeroes_mean():
    projection = project_player(
        weekly_points=[10, 15, 20],
        recent_share=0.25,
        season_share=0.25,
        opponent_points_allowed=20,
        league_avg_points_allowed=20,
        weeks_played=8,
        status="Out",
    )
    assert projection.mean == 0.0


def test_project_player_questionable_discount_applied():
    projection = project_player(
        weekly_points=[20, 20, 20],
        recent_share=0.3,
        season_share=0.3,
        opponent_points_allowed=10,
        league_avg_points_allowed=10,
        weeks_played=8,
        status="Questionable",
    )
    assert projection.mean == 17.0
    assert projection.floor == 17.0
    assert projection.ceiling == 17.0
    assert projection.components["availability_multiplier"] == 0.85


def test_project_player_no_history_does_not_crash():
    projection = project_player(
        weekly_points=[],
        recent_share=0.2,
        season_share=0.2,
        opponent_points_allowed=20,
        league_avg_points_allowed=20,
        weeks_played=0,
        status="Active",
    )
    assert projection.mean == 0.0
    assert projection.floor == 0.0
    assert projection.ceiling == 0.0
    assert projection.std == 0.0
