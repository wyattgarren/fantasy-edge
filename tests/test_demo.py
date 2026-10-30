from data.demo import DEMO_LEAGUE_ID, DEMO_USER_ID, DemoSleeperClient


def test_demo_client_is_internally_consistent() -> None:
    client = DemoSleeperClient()

    league = client.get_league(DEMO_LEAGUE_ID)
    rosters = client.get_rosters(DEMO_LEAGUE_ID)
    league_users = client.get_league_users(DEMO_LEAGUE_ID)
    players = client.get_players()
    user = client.get_user("demo")
    matchups = client.get_matchups(DEMO_LEAGUE_ID, 7)
    trending = client.get_trending()

    assert league.league_id == DEMO_LEAGUE_ID
    assert len(rosters) > 1
    assert all(roster.league_id == DEMO_LEAGUE_ID for roster in rosters)

    my_roster = next(r for r in rosters if r.owner_id == DEMO_USER_ID)
    assert my_roster is not None

    for roster in rosters:
        for player_id in roster.starters:
            if player_id == "0":
                continue  # Sleeper's placeholder for an empty starting slot
            assert player_id in players, f"starter {player_id} missing from players"

    assert user.user_id == DEMO_USER_ID
    assert {u.user_id for u in league_users}  # non-empty
    assert len(matchups) == len(rosters)
    assert all(m.points > 0 for m in matchups), "demo matchups must be from an already-scored week"
    assert isinstance(trending, list)


def test_demo_client_get_leagues_returns_the_demo_league() -> None:
    client = DemoSleeperClient()

    leagues = client.get_leagues(DEMO_USER_ID, "2026")

    assert len(leagues) == 1
    assert leagues[0].league_id == DEMO_LEAGUE_ID


def test_demo_client_close_and_context_manager_are_noops() -> None:
    with DemoSleeperClient() as client:
        client.get_league(DEMO_LEAGUE_ID)
    # exiting the context manager must not raise
