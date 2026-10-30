import httpx
import pytest

from data.exceptions import LeagueNotFoundError, SleeperUnavailableError, UserNotFoundError
from data.sleeper import BASE_URL, SleeperClient

USER_ID = "973394056015360000"
LEAGUE_ID = "1391465605172834304"
SEASON = "2026"
WEEK = 8


def test_get_user(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/user/thesplurggler").respond(json=load_fixture("user.json"))
    client = SleeperClient(cache=cache)

    user = client.get_user("thesplurggler")

    assert user.user_id == USER_ID
    assert user.username == "thesplurggler"


def test_get_user_not_found(respx_mock, cache):
    # Sleeper responds 200 with a literal JSON `null` body for an unknown
    # username (confirmed against the live API) -- json=None would instead
    # send an empty body, so set the literal text explicitly.
    respx_mock.get(f"{BASE_URL}/user/doesnotexist").respond(text="null")
    client = SleeperClient(cache=cache)

    with pytest.raises(UserNotFoundError):
        client.get_user("doesnotexist")


def test_get_leagues(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/user/{USER_ID}/leagues/nfl/{SEASON}").respond(
        json=load_fixture("leagues.json")
    )
    client = SleeperClient(cache=cache)

    leagues = client.get_leagues(USER_ID, SEASON)

    assert any(league.league_id == LEAGUE_ID for league in leagues)


def test_get_league(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/league/{LEAGUE_ID}").respond(json=load_fixture("league.json"))
    client = SleeperClient(cache=cache)

    league = client.get_league(LEAGUE_ID)

    assert league.league_id == LEAGUE_ID
    assert league.total_rosters == 12
    assert "QB" in league.roster_positions
    assert league.scoring_settings["rec"] == 1.0


def test_get_league_not_found(respx_mock, cache):
    respx_mock.get(f"{BASE_URL}/league/0").respond(status_code=404, json=None)
    client = SleeperClient(cache=cache)

    with pytest.raises(LeagueNotFoundError):
        client.get_league("0")


def test_get_rosters(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/league/{LEAGUE_ID}/rosters").respond(
        json=load_fixture("rosters.json")
    )
    client = SleeperClient(cache=cache)

    rosters = client.get_rosters(LEAGUE_ID)

    assert len(rosters) == 12
    assert all(roster.league_id == LEAGUE_ID for roster in rosters)


def test_get_league_users(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/league/{LEAGUE_ID}/users").respond(
        json=load_fixture("league_users.json")
    )
    client = SleeperClient(cache=cache)

    users = client.get_league_users(LEAGUE_ID)

    assert any(user.display_name == "thesplurggler" for user in users)


def test_get_matchups(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/league/{LEAGUE_ID}/matchups/{WEEK}").respond(
        json=load_fixture("matchups_week8.json")
    )
    client = SleeperClient(cache=cache)

    matchups = client.get_matchups(LEAGUE_ID, WEEK)

    assert len(matchups) == 12
    assert all(m.matchup_id is not None for m in matchups)


def test_get_transactions(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/league/{LEAGUE_ID}/transactions/{WEEK}").respond(
        json=load_fixture("transactions_week8.json")
    )
    client = SleeperClient(cache=cache)

    transactions = client.get_transactions(LEAGUE_ID, WEEK)

    assert len(transactions) > 0
    assert all(t.type for t in transactions)


def test_get_nfl_state(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/state/nfl").respond(json=load_fixture("nfl_state.json"))
    client = SleeperClient(cache=cache)

    state = client.get_nfl_state()

    assert state.week == WEEK
    assert state.season == SEASON


def test_get_trending(respx_mock, load_fixture, cache):
    respx_mock.get(f"{BASE_URL}/players/nfl/trending/add?lookback_hours=24&limit=10").respond(
        json=load_fixture("trending_add.json")
    )
    client = SleeperClient(cache=cache)

    trending = client.get_trending(type="add", lookback_hours=24, limit=10)

    assert len(trending) == 10
    assert trending[0].count > 0


def test_get_players_parses_and_caches(respx_mock, load_fixture, cache):
    route = respx_mock.get(f"{BASE_URL}/players/nfl").respond(
        json=load_fixture("players_sample.json")
    )
    client = SleeperClient(cache=cache)

    first = client.get_players()
    second = client.get_players()

    assert route.call_count == 1  # second call served from the file cache
    assert second == first
    assert "DEN" in first
    assert first["DEN"].position == "DEF"


def test_retries_once_then_succeeds(respx_mock, load_fixture, cache):
    route = respx_mock.get(f"{BASE_URL}/state/nfl")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json=load_fixture("nfl_state.json")),
    ]
    client = SleeperClient(cache=cache)

    state = client.get_nfl_state()

    assert state.week == WEEK
    assert route.call_count == 2


def test_unavailable_after_retry_fails(respx_mock, cache):
    route = respx_mock.get(f"{BASE_URL}/state/nfl")
    route.side_effect = [httpx.Response(500), httpx.Response(500)]
    client = SleeperClient(cache=cache)

    with pytest.raises(SleeperUnavailableError):
        client.get_nfl_state()

    assert route.call_count == 2
