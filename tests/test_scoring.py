import pytest

from core.scoring import score_stat_line


@pytest.fixture
def scoring_settings(load_fixture):
    return load_fixture("league.json")["scoring_settings"]


def test_wr_receiving_line(scoring_settings):
    stats = {"rec": 5, "rec_yd": 64, "rec_td": 1}
    # full PPR: 5*1.0 + 64*0.1 + 1*6.0
    assert score_stat_line(stats, scoring_settings) == 17.4


def test_rb_rush_and_catch_line(scoring_settings):
    stats = {"rush_att": 18, "rush_yd": 92, "rush_td": 1, "rec": 3, "rec_yd": 20}
    # rush_att scores 0 in this league; 92*0.1 + 6.0 + 3*1.0 + 20*0.1
    assert score_stat_line(stats, scoring_settings) == 20.2


def test_qb_passing_line(scoring_settings):
    stats = {"pass_yd": 275, "pass_td": 2, "pass_int": 1, "rush_yd": 15}
    # 275*0.04 + 2*4.0 + 1*-2.0 + 15*0.1
    assert score_stat_line(stats, scoring_settings) == 18.5


def test_unknown_stat_key_scores_zero(scoring_settings):
    assert score_stat_line({"not_a_real_stat": 100}, scoring_settings) == 0.0


def test_empty_stat_line_scores_zero(scoring_settings):
    assert score_stat_line({}, scoring_settings) == 0.0
