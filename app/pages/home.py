import streamlit as st

from app.client import get_client
from app.state import save_to_query_params
from data.exceptions import SleeperAPIError, UserNotFoundError

st.title("Connect your Sleeper league")

client = get_client()

username_input = st.text_input("Sleeper username", value=st.session_state.get("username", ""))
find_clicked = st.button("Find leagues", type="primary")

if find_clicked and username_input:
    try:
        user = client.get_user(username_input)
    except UserNotFoundError:
        st.error(f"No Sleeper user named {username_input!r}.")
        st.stop()
    except SleeperAPIError as exc:
        st.error(f"Sleeper is unavailable right now ({exc}).")
        st.stop()
    st.session_state["username"] = username_input
    st.session_state["user_id"] = user.user_id
    st.session_state.pop("league_id", None)
    st.session_state.pop("roster_id", None)

user_id = st.session_state.get("user_id")
if not user_id:
    st.info('Enter your Sleeper username and click "Find leagues" to get started.')
    st.stop()

try:
    nfl_state = client.get_nfl_state()
except SleeperAPIError as exc:
    st.error(f"Sleeper is unavailable right now ({exc}).")
    st.stop()

season_options = [nfl_state.season, str(int(nfl_state.season) - 1)]
default_season = st.session_state.get("season", nfl_state.season)
season = st.selectbox(
    "Season",
    season_options,
    index=season_options.index(default_season) if default_season in season_options else 0,
)

try:
    leagues = client.get_leagues(user_id, season)
except SleeperAPIError as exc:
    st.error(f"Sleeper is unavailable right now ({exc}).")
    st.stop()

if not leagues:
    st.info(f"No leagues found for {st.session_state['username']} in {season}.")
    st.stop()

league_names = {league.league_id: league.name.strip() for league in leagues}
league_ids = list(league_names)
default_league_id = st.session_state.get("league_id")
if default_league_id not in league_ids:
    default_league_id = league_ids[0]
league_id = st.selectbox(
    "League",
    league_ids,
    index=league_ids.index(default_league_id),
    format_func=lambda lid: league_names[lid],
)

rosters = client.get_rosters(league_id)
league_users = client.get_league_users(league_id)
names_by_user_id = {u.user_id: (u.display_name or u.user_id) for u in league_users}

team_labels = {
    roster.roster_id: (
        f"{names_by_user_id.get(roster.owner_id, 'Unclaimed team')} "
        f"({roster.settings.get('wins', 0)}-{roster.settings.get('losses', 0)})"
    )
    for roster in rosters
}
roster_ids = list(team_labels)
my_roster_id = next((r.roster_id for r in rosters if r.owner_id == user_id), roster_ids[0])
default_roster_id = st.session_state.get("roster_id", my_roster_id)
if default_roster_id not in roster_ids:
    default_roster_id = my_roster_id

roster_id = st.selectbox(
    "Your team",
    roster_ids,
    index=roster_ids.index(default_roster_id),
    format_func=lambda rid: team_labels[rid],
)

if st.button("Connect", type="primary"):
    st.session_state["season"] = season
    st.session_state["league_id"] = league_id
    st.session_state["roster_id"] = roster_id
    save_to_query_params()
    st.success("Connected! Opening My Team...")
    st.switch_page("pages/my_team.py")
