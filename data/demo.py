"""A SleeperClient look-alike backed by a frozen, bundled snapshot instead
of the live API, so a visitor with no Sleeper account can try every page
with realistic numbers and zero network calls. See data/stats.py's `demo=`
kwarg for the matching nflreadpy-side snapshot.

Duck-types data.sleeper.SleeperClient's public surface rather than
subclassing it, since every method here has a completely different (static,
file-backed) implementation.
"""

from __future__ import annotations

import json
from pathlib import Path

from data.models import (
    League,
    LeagueUser,
    Matchup,
    NFLState,
    Player,
    Roster,
    SleeperUser,
    TrendingPlayer,
    Transaction,
)

DEMO_DATA_DIR = Path(__file__).resolve().parent / "demo_data" / "sleeper"

DEMO_USERNAME = "demo"
DEMO_USER_ID = "demo"
DEMO_LEAGUE_ID = "demo"


def _load(name: str) -> object:
    return json.loads((DEMO_DATA_DIR / name).read_text())


class DemoSleeperClient:
    """No cache, no network -- everything is read from bundled JSON once."""

    def __init__(self) -> None:
        self._user = SleeperUser.model_validate(_load("user.json"))
        self._league = League.model_validate(_load("league.json"))
        self._rosters = [Roster.model_validate(r) for r in _load("rosters.json")]
        self._league_users = [LeagueUser.model_validate(u) for u in _load("league_users.json")]
        self._matchups = [Matchup.model_validate(m) for m in _load("matchups.json")]
        self._transactions = [Transaction.model_validate(t) for t in _load("transactions.json")]
        self._trending = [TrendingPlayer.model_validate(t) for t in _load("trending_add.json")]
        self._nfl_state = NFLState.model_validate(_load("nfl_state.json"))
        self._players = {
            player_id: Player.model_validate({**raw, "player_id": player_id})
            for player_id, raw in _load("players.json").items()
        }

    def close(self) -> None:
        pass

    def __enter__(self) -> "DemoSleeperClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        pass

    def get_user(self, username: str) -> SleeperUser:
        return self._user

    def get_leagues(self, user_id: str, season: str) -> list[League]:
        return [self._league]

    def get_league(self, league_id: str) -> League:
        return self._league

    def get_rosters(self, league_id: str) -> list[Roster]:
        return self._rosters

    def get_league_users(self, league_id: str) -> list[LeagueUser]:
        return self._league_users

    def get_matchups(self, league_id: str, week: int) -> list[Matchup]:
        return self._matchups

    def get_transactions(self, league_id: str, week: int) -> list[Transaction]:
        return self._transactions

    def get_nfl_state(self) -> NFLState:
        return self._nfl_state

    def get_players(self) -> dict[str, Player]:
        return self._players

    def get_trending(
        self, type: str = "add", lookback_hours: int = 24, limit: int = 25
    ) -> list[TrendingPlayer]:
        return self._trending[:limit]
