from core.simulate import PlayerDistribution, simulate_matchup


def test_average_matches_sum_of_projections():
    # means well above std so clipping at 0 is never triggered -- the
    # simulated average should converge tightly to the sum of means
    my_players = [
        PlayerDistribution("a", mean=20, std=3),
        PlayerDistribution("b", mean=15, std=2),
        PlayerDistribution("c", mean=10, std=2),
    ]
    opponent_players = [
        PlayerDistribution("x", mean=20, std=3),
        PlayerDistribution("y", mean=15, std=2),
    ]

    result = simulate_matchup(my_players, opponent_players, runs=10000, seed=42)

    assert abs(result.my_mean - 45.0) < 1.0
    assert abs(result.opponent_mean - 35.0) < 1.0


def test_fixed_seed_is_reproducible():
    my_players = [PlayerDistribution("a", mean=20, std=5), PlayerDistribution("b", mean=10, std=3)]
    opponent_players = [PlayerDistribution("x", mean=18, std=4)]

    result_1 = simulate_matchup(my_players, opponent_players, runs=2000, seed=123)
    result_2 = simulate_matchup(my_players, opponent_players, runs=2000, seed=123)

    assert result_1 == result_2


def test_win_probability_favors_much_better_team():
    my_players = [PlayerDistribution("a", mean=50, std=2)]
    opponent_players = [PlayerDistribution("x", mean=5, std=2)]

    result = simulate_matchup(my_players, opponent_players, runs=5000, seed=1)

    assert result.win_probability > 0.99


def test_win_probability_near_half_for_evenly_matched_teams():
    my_players = [PlayerDistribution("a", mean=20, std=5)]
    opponent_players = [PlayerDistribution("x", mean=20, std=5)]

    result = simulate_matchup(my_players, opponent_players, runs=5000, seed=1)

    assert 0.4 < result.win_probability < 0.6


def test_swing_players_ranks_high_variance_player_first():
    my_players = [
        PlayerDistribution("volatile", mean=20, std=10),
        PlayerDistribution("steady", mean=20, std=0.001),
    ]
    opponent_players = [PlayerDistribution("opp", mean=20, std=5)]

    result = simulate_matchup(my_players, opponent_players, runs=5000, seed=7)

    swing_by_player = dict(result.swing_players)
    assert abs(swing_by_player["volatile"]) > abs(swing_by_player["steady"])
    assert result.swing_players[0][0] == "volatile"  # sorted by |swing| desc


def test_floor_is_below_ceiling_and_mean_between():
    my_players = [PlayerDistribution("a", mean=20, std=5)]
    opponent_players = [PlayerDistribution("x", mean=18, std=5)]

    result = simulate_matchup(my_players, opponent_players, runs=5000, seed=1)

    assert result.my_floor < result.my_mean < result.my_ceiling
