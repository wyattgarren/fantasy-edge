"""Records real Sleeper API responses into tests/fixtures/*.json for offline tests.

Run manually (requires network access):

    python scripts/record_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

BASE_URL = "https://api.sleeper.app/v1"
USERNAME = "thesplurggler"
LEAGUE_ID = "1391465605172834304"
SEASON = "2026"
WEEK = 8

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def write_fixture(name: str, data: object) -> None:
    path = FIXTURES_DIR / name
    path.write_text(json.dumps(data, indent=2))
    print(f"wrote {path.relative_to(FIXTURES_DIR.parent.parent)}")


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        nfl_state = client.get("/state/nfl").json()
        write_fixture("nfl_state.json", nfl_state)

        user = client.get(f"/user/{USERNAME}").json()
        write_fixture("user.json", user)
        user_id = user["user_id"]

        leagues = client.get(f"/user/{user_id}/leagues/nfl/{SEASON}").json()
        write_fixture("leagues.json", leagues)

        league = client.get(f"/league/{LEAGUE_ID}").json()
        write_fixture("league.json", league)

        rosters = client.get(f"/league/{LEAGUE_ID}/rosters").json()
        write_fixture("rosters.json", rosters)

        league_users = client.get(f"/league/{LEAGUE_ID}/users").json()
        write_fixture("league_users.json", league_users)

        matchups = client.get(f"/league/{LEAGUE_ID}/matchups/{WEEK}").json()
        write_fixture("matchups_week8.json", matchups)

        transactions = client.get(f"/league/{LEAGUE_ID}/transactions/{WEEK}").json()
        write_fixture("transactions_week8.json", transactions)

        trending_add = client.get(
            "/players/nfl/trending/add", params={"lookback_hours": 24, "limit": 10}
        ).json()
        write_fixture("trending_add.json", trending_add)

        # /players/nfl is ~14MB; trim to just the players on this league's
        # rosters so the fixture stays real but repo-sized.
        all_players = client.get("/players/nfl").json()
        roster_player_ids = {
            player_id for roster in rosters for player_id in roster.get("players") or []
        }
        players_sample = {
            player_id: all_players[player_id]
            for player_id in roster_player_ids
            if player_id in all_players
        }
        write_fixture("players_sample.json", players_sample)


if __name__ == "__main__":
    main()
