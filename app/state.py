"""Session-state <-> URL query-param glue for the connected league/team.

Only `user` (Sleeper username) and `league` (league_id) round-trip through
the URL, matching the roadmap's `?league=...&user=...` link format. Season
and roster_id are resolved/selected within the session.
"""

from __future__ import annotations

import streamlit as st

from data.exceptions import SleeperAPIError
from data.sleeper import SleeperClient

QUERY_PARAMS = {"user": "username", "league": "league_id"}


def load_from_query_params() -> None:
    for param, key in QUERY_PARAMS.items():
        if key not in st.session_state and param in st.query_params:
            st.session_state[key] = st.query_params[param]


def save_to_query_params() -> None:
    for param, key in QUERY_PARAMS.items():
        value = st.session_state.get(key)
        if value is not None:
            st.query_params[param] = str(value)


def ensure_connected(client: SleeperClient) -> None:
    """Resolves user_id/roster_id from a username/league_id that arrived via
    URL params (or a prior session), so a shared link can open straight into
    a league without re-running the home-page picker."""
    if "user_id" not in st.session_state and st.session_state.get("username"):
        try:
            user = client.get_user(st.session_state["username"])
        except SleeperAPIError:
            pass
        else:
            st.session_state["user_id"] = user.user_id

    if "roster_id" not in st.session_state and st.session_state.get("league_id"):
        try:
            rosters = client.get_rosters(st.session_state["league_id"])
        except SleeperAPIError:
            pass
        else:
            user_id = st.session_state.get("user_id")
            mine = next((r for r in rosters if r.owner_id == user_id), None)
            if mine is not None:
                st.session_state["roster_id"] = mine.roster_id


def is_connected() -> bool:
    return bool(st.session_state.get("league_id")) and bool(st.session_state.get("roster_id"))
