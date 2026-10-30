"""Typed, cached client for the read-only Sleeper API (https://api.sleeper.app/v1)."""

from __future__ import annotations

from typing import Any

import httpx

from data.cache import FileCache
from data.exceptions import (
    LeagueNotFoundError,
    SleeperAPIError,
    SleeperUnavailableError,
    UserNotFoundError,
)
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

BASE_URL = "https://api.sleeper.app/v1"
PLAYERS_CACHE_KEY = "players"
PLAYERS_TTL_SECONDS = 24 * 60 * 60


class SleeperClient:
    def __init__(self, cache: FileCache, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=BASE_URL, timeout=10.0)
        self._cache = cache

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SleeperClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _get(self, path: str, *, not_found_exc: type[SleeperAPIError] = SleeperAPIError) -> Any:
        last_error: Exception | None = None
        for _ in range(2):  # one retry
            try:
                response = self._client.get(path)
            except httpx.TransportError as exc:
                last_error = exc
                continue
            if response.status_code == 404:
                raise not_found_exc(f"{path} returned 404")
            if response.status_code >= 500:
                last_error = SleeperUnavailableError(f"{path} returned {response.status_code}")
                continue
            if response.status_code >= 400:
                raise SleeperAPIError(f"{path} returned {response.status_code}")
            return response.json()
        raise SleeperUnavailableError(f"Sleeper unavailable after retry: {path}") from last_error

    def get_user(self, username: str) -> SleeperUser:
        data = self._get(f"/user/{username}")
        if data is None:
            raise UserNotFoundError(f"user {username!r} not found")
        return SleeperUser.model_validate(data)

    def get_leagues(self, user_id: str, season: str) -> list[League]:
        data = self._get(f"/user/{user_id}/leagues/nfl/{season}")
        return [League.model_validate(item) for item in data]

    def get_league(self, league_id: str) -> League:
        data = self._get(f"/league/{league_id}", not_found_exc=LeagueNotFoundError)
        return League.model_validate(data)

    def get_rosters(self, league_id: str) -> list[Roster]:
        data = self._get(f"/league/{league_id}/rosters", not_found_exc=LeagueNotFoundError)
        return [Roster.model_validate(item) for item in data]

    def get_league_users(self, league_id: str) -> list[LeagueUser]:
        data = self._get(f"/league/{league_id}/users", not_found_exc=LeagueNotFoundError)
        return [LeagueUser.model_validate(item) for item in data]

    def get_matchups(self, league_id: str, week: int) -> list[Matchup]:
        data = self._get(
            f"/league/{league_id}/matchups/{week}", not_found_exc=LeagueNotFoundError
        )
        return [Matchup.model_validate(item) for item in data]

    def get_transactions(self, league_id: str, week: int) -> list[Transaction]:
        data = self._get(
            f"/league/{league_id}/transactions/{week}", not_found_exc=LeagueNotFoundError
        )
        return [Transaction.model_validate(item) for item in data]

    def get_nfl_state(self) -> NFLState:
        data = self._get("/state/nfl")
        return NFLState.model_validate(data)

    def get_players(self) -> dict[str, Player]:
        cached = self._cache.get(PLAYERS_CACHE_KEY)
        if cached is None:
            cached = self._get("/players/nfl")
            self._cache.set(PLAYERS_CACHE_KEY, cached, PLAYERS_TTL_SECONDS)
        return {
            player_id: Player.model_validate({**raw, "player_id": player_id})
            for player_id, raw in cached.items()
        }

    def get_trending(
        self, type: str = "add", lookback_hours: int = 24, limit: int = 25
    ) -> list[TrendingPlayer]:
        data = self._get(
            f"/players/nfl/trending/{type}?lookback_hours={lookback_hours}&limit={limit}"
        )
        return [TrendingPlayer.model_validate(item) for item in data]
