"""Typed models for the subset of the Sleeper API this app uses.

Unknown fields on each payload are ignored (pydantic's default), since
Sleeper's raw objects carry many fields this app doesn't need.
"""

from __future__ import annotations

from pydantic import BaseModel


class SleeperUser(BaseModel):
    user_id: str
    username: str
    display_name: str | None = None
    avatar: str | None = None


class League(BaseModel):
    league_id: str
    name: str
    season: str
    season_type: str
    status: str
    sport: str
    total_rosters: int
    roster_positions: list[str]
    scoring_settings: dict[str, float]
    settings: dict[str, object] = {}
    previous_league_id: str | None = None
    avatar: str | None = None


class Roster(BaseModel):
    roster_id: int
    league_id: str
    owner_id: str | None = None
    players: list[str] = []
    starters: list[str] = []
    reserve: list[str] | None = None
    taxi: list[str] | None = None
    settings: dict[str, object] = {}


class LeagueUser(BaseModel):
    user_id: str
    display_name: str | None = None
    avatar: str | None = None
    is_owner: bool | None = None
    metadata: dict[str, object] | None = None


class Matchup(BaseModel):
    roster_id: int
    matchup_id: int | None = None
    points: float = 0.0
    players: list[str] = []
    starters: list[str] = []
    starters_points: list[float] = []
    players_points: dict[str, float] = {}


class Transaction(BaseModel):
    transaction_id: str
    type: str
    status: str
    created: int
    roster_ids: list[int] = []
    adds: dict[str, int] | None = None
    drops: dict[str, int] | None = None
    leg: int | None = None


class NFLState(BaseModel):
    week: int
    season: str
    season_type: str
    display_week: int
    league_season: str
    previous_season: str | None = None
    season_start_date: str | None = None
    season_has_scores: bool | None = None


class Player(BaseModel):
    player_id: str
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    team: str | None = None
    position: str | None = None
    status: str | None = None
    injury_status: str | None = None
    number: int | None = None


class TrendingPlayer(BaseModel):
    player_id: str
    count: int
