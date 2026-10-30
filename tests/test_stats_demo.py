import data.stats as stats


def test_load_weekly_stats_demo_is_offline_and_nonempty() -> None:
    df = stats.load_weekly_stats("2026", demo=True)

    assert df.height > 0
    assert "player_id" in df.columns
    assert "week" in df.columns


def test_load_snap_counts_demo_is_offline_and_nonempty() -> None:
    df = stats.load_snap_counts("2026", demo=True)

    assert df.height > 0
    assert "pfr_player_id" in df.columns
    assert "offense_pct" in df.columns


def test_load_schedules_demo_is_offline_and_nonempty() -> None:
    df = stats.load_schedules("2026", demo=True)

    assert df.height > 0
    assert "home_team" in df.columns
    assert "away_team" in df.columns


def test_load_player_id_map_demo_is_offline_and_nonempty() -> None:
    df = stats.load_player_id_map(demo=True)

    assert df.height > 0
    assert {"sleeper_id", "gsis_id", "pfr_id"}.issubset(df.columns)


def test_load_expected_points_demo_is_offline_and_nonempty() -> None:
    df = stats.load_expected_points("2026", demo=True)

    assert df.height > 0
    assert {"player_id", "week", "total_fantasy_points", "total_fantasy_points_exp"}.issubset(
        df.columns
    )


def test_load_player_ages_demo_is_offline_and_nonempty() -> None:
    df = stats.load_player_ages(demo=True)

    assert df.height > 0
    assert {"sleeper_id", "age", "position"}.issubset(df.columns)
