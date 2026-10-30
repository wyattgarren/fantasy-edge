from statistics import mean

from core.backtest import PlayerSeries, backtest


def _mean_predict_fn(prior, player):
    return mean(prior)


def test_mae_against_hand_built_data():
    players = [PlayerSeries(position="WR", weekly_points=[10, 20, 30])]

    result = backtest(players, start_week=2, end_week=3, predict_fn=_mean_predict_fn)

    # week 2: prior=[10], actual=20, model/season_avg pred=10 (error 10), last_week pred=10 (error 10)
    # week 3: prior=[10,20], actual=30, model/season_avg pred=15 (error 15), last_week pred=20 (error 10)
    assert result.weeks_tested == [2, 3]
    assert result.model_mae_by_position == {"WR": 12.5}
    assert result.season_avg_mae_by_position == {"WR": 12.5}
    assert result.last_week_mae_by_position == {"WR": 10.0}


def test_separates_mae_by_position():
    players = [
        PlayerSeries(position="WR", weekly_points=[10, 10, 10]),
        PlayerSeries(position="RB", weekly_points=[5, 5, 100]),
    ]

    result = backtest(players, start_week=2, end_week=3, predict_fn=_mean_predict_fn)

    assert result.model_mae_by_position["WR"] == 0.0
    assert result.model_mae_by_position["RB"] > 0.0
    assert set(result.model_mae_by_position) == {"WR", "RB"}


def test_skips_weeks_with_no_prior_data():
    players = [PlayerSeries(position="QB", weekly_points=[10, 20, 30])]

    # start_week=1 has no prior weeks at all and must be skipped, not crash
    result = backtest(players, start_week=1, end_week=2, predict_fn=_mean_predict_fn)

    assert result.weeks_tested == [2]


def test_no_leakage_future_weeks_never_change_earlier_predictions():
    base_points = [12.0, 8.0, 15.0, 9.0, 11.0]
    with_future = base_points + [9999.0]  # week 6, far outside the tested range

    without_future_result = backtest(
        [PlayerSeries(position="RB", weekly_points=base_points)],
        start_week=2,
        end_week=5,
        predict_fn=_mean_predict_fn,
    )
    with_future_result = backtest(
        [PlayerSeries(position="RB", weekly_points=with_future)],
        start_week=2,
        end_week=5,
        predict_fn=_mean_predict_fn,
    )

    assert with_future_result == without_future_result


def test_no_leakage_predict_fn_only_ever_sees_prior_weeks():
    seen_priors = []

    def recording_predict_fn(prior: list[float], player: PlayerSeries) -> float:
        seen_priors.append(list(prior))
        return mean(prior)

    weekly_points = [10.0, 20.0, 30.0, 9999.0]  # week 4 is an extreme outlier
    backtest(
        [PlayerSeries(position="TE", weekly_points=weekly_points)],
        start_week=2,
        end_week=3,
        predict_fn=recording_predict_fn,
    )

    assert seen_priors == [[10.0], [10.0, 20.0]]
    assert all(9999.0 not in prior for prior in seen_priors)


def test_predict_fn_receives_player_for_per_player_context():
    # predict_fn can key off player.player_id to look up player-specific
    # context (e.g. opponent/opportunity history) rather than one formula
    # shared across every player.
    offsets = {"a": 100.0, "b": 200.0}

    def offset_predict_fn(prior, player):
        return offsets[player.player_id]

    players = [
        PlayerSeries(position="WR", weekly_points=[1.0, 2.0], player_id="a"),
        PlayerSeries(position="WR", weekly_points=[1.0, 2.0], player_id="b"),
    ]
    result = backtest(players, start_week=2, end_week=2, predict_fn=offset_predict_fn)

    # error for "a": |100-2|=98, for "b": |200-2|=198 -> mean=148
    assert result.model_mae_by_position["WR"] == 148.0
