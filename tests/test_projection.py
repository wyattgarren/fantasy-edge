from core.projection import (
    GAME_SCRIPT_SPREAD_COEFFICIENT,
    GAME_SCRIPT_TOTAL_COEFFICIENTS,
    NEUTRAL_TOTAL,
    availability_multiplier,
    baseline_points,
    game_script_adjustment,
    matchup_adjustment,
    opportunity_adjustment,
    practice_participation_adjustment,
    project_player,
    red_zone_adjustment,
    regression_adjustment,
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


def test_regression_adjustment_known_value():
    # ratio=0.4 (no clamp needed), full shrinkage -> -0.5*0.4*20*1.0
    assert regression_adjustment(0.4, baseline=20, weeks_played=8) == -4.0


def test_regression_adjustment_clamps_extreme_ratio():
    # ratio clamped from 0.8 to max_ratio 0.5 -> -0.5*0.5*20*1.0
    assert regression_adjustment(0.8, baseline=20, weeks_played=8) == -5.0


def test_regression_adjustment_partial_shrinkage():
    # shrinkage = 4/8 = 0.5 -> -0.5*0.4*20*0.5
    assert regression_adjustment(0.4, baseline=20, weeks_played=4) == -2.0


def test_regression_adjustment_negative_ratio_is_a_positive_boost():
    # underperforming their own expectation (bad luck) -> adjustment helps them
    assert regression_adjustment(-0.4, baseline=20, weeks_played=8) == 4.0


def test_game_script_adjustment_rb_spread_effect():
    # RB, favored by 10, total at exactly neutral -> only the spread term applies
    result = game_script_adjustment("RB", team_spread=10.0, total_line=NEUTRAL_TOTAL)
    assert round(result, 4) == round(GAME_SCRIPT_SPREAD_COEFFICIENT * 10.0, 4)


def test_game_script_adjustment_non_rb_has_no_spread_effect():
    # WR, favored by 10, total at exactly neutral -> spread is RB-only, so 0
    result = game_script_adjustment("WR", team_spread=10.0, total_line=NEUTRAL_TOTAL)
    assert result == 0.0


def test_game_script_adjustment_total_effect_is_position_specific():
    result = game_script_adjustment("WR", team_spread=0.0, total_line=NEUTRAL_TOTAL + 10.0)
    assert round(result, 4) == round(GAME_SCRIPT_TOTAL_COEFFICIENTS["WR"] * 10.0, 4)


def test_game_script_adjustment_rb_total_effect_is_zero():
    # empirically ~0 -- total doesn't move RB production like it does the passing game
    result = game_script_adjustment("RB", team_spread=0.0, total_line=NEUTRAL_TOTAL + 10.0)
    assert result == 0.0


def test_game_script_adjustment_clamps_extreme_spread():
    # team_spread=30 clamps to the 17.0 bound
    result = game_script_adjustment("RB", team_spread=30.0, total_line=NEUTRAL_TOTAL)
    assert round(result, 4) == round(GAME_SCRIPT_SPREAD_COEFFICIENT * 17.0, 4)


def test_game_script_adjustment_clamps_extreme_total():
    # total 50 points above neutral clamps to the 12.0 bound
    result = game_script_adjustment("QB", team_spread=0.0, total_line=NEUTRAL_TOTAL + 50.0)
    assert round(result, 4) == round(GAME_SCRIPT_TOTAL_COEFFICIENTS["QB"] * 12.0, 4)


def test_game_script_adjustment_unknown_position_is_zero():
    assert game_script_adjustment("K", team_spread=10.0, total_line=NEUTRAL_TOTAL + 10.0) == 0.0


def test_practice_participation_adjustment_no_report_is_full_trust():
    assert practice_participation_adjustment(None) == 1.0


def test_practice_participation_adjustment_full_participation():
    assert practice_participation_adjustment("Full Participation in Practice") == 1.0


def test_practice_participation_adjustment_limited():
    assert practice_participation_adjustment("Limited Participation in Practice") == 0.9


def test_practice_participation_adjustment_dnp():
    assert practice_participation_adjustment("Did Not Participate In Practice") == 0.75


def test_practice_participation_adjustment_matches_by_substring_case_insensitive():
    # real nflreadpy values vary in capitalization/wording -- substring match, not exact
    assert practice_participation_adjustment("did not participate in practice") == 0.75


def test_red_zone_adjustment_matches_opportunity_adjustment_at_full_shrinkage():
    # at weeks_played >= shrinkage_full_weeks, red_zone_adjustment should
    # exactly reproduce the reused opportunity_adjustment math
    recent_share, season_share, baseline = 0.3, 0.2, 20.0
    expected = opportunity_adjustment(recent_share, season_share, baseline)
    assert red_zone_adjustment(recent_share, season_share, baseline, weeks_played=8) == expected


def test_red_zone_adjustment_shrinks_early_season():
    recent_share, season_share, baseline = 0.3, 0.2, 20.0
    full = red_zone_adjustment(recent_share, season_share, baseline, weeks_played=8)
    partial = red_zone_adjustment(recent_share, season_share, baseline, weeks_played=2)
    assert partial == full * 0.5  # weeks_played=2 / shrinkage_full_weeks=4


def test_red_zone_adjustment_zero_weeks_played_is_zero():
    assert red_zone_adjustment(0.3, 0.2, baseline=20.0, weeks_played=0) == 0.0


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
