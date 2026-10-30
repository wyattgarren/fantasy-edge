import streamlit as st

from app.client import get_client
from app.components import demo_mode, page_caption
from data.exceptions import SleeperAPIError

st.title("League")

if not st.session_state.get("league_id"):
    st.info("Connect a league on the Home page first.")
    if st.button("Go to Home"):
        st.switch_page("pages/home.py")
    st.stop()

client = get_client(demo_mode())
league_id = st.session_state["league_id"]
my_roster_id = st.session_state.get("roster_id")

try:
    league = client.get_league(league_id)
    rosters = client.get_rosters(league_id)
    league_users = client.get_league_users(league_id)
    players = client.get_players()
except SleeperAPIError as exc:
    st.error(f"Sleeper is unavailable right now ({exc}).")
    st.stop()

names_by_user_id = {u.user_id: (u.display_name or u.user_id) for u in league_users}
page_caption(league.name, league.season)


def combined_points(settings: dict, whole_key: str, decimal_key: str) -> float:
    return settings.get(whole_key, 0) + settings.get(decimal_key, 0) / 100


standings = []
for roster in rosters:
    settings = roster.settings
    team_name = names_by_user_id.get(roster.owner_id, "Unclaimed team")
    if roster.roster_id == my_roster_id:
        team_name += " (You)"
    standings.append(
        {
            "roster_id": roster.roster_id,
            "Team": team_name,
            "W": settings.get("wins", 0),
            "L": settings.get("losses", 0),
            "T": settings.get("ties", 0),
            "PF": combined_points(settings, "fpts", "fpts_decimal"),
            "PA": combined_points(settings, "fpts_against", "fpts_against_decimal"),
        }
    )
standings.sort(key=lambda row: (-row["W"], -row["PF"]))

st.subheader("Standings")
st.dataframe(
    [{k: v for k, v in row.items() if k != "roster_id"} for row in standings],
    hide_index=True,
)

st.subheader("Rosters")
team_options = {row["roster_id"]: row["Team"] for row in standings}
selected_roster_id = st.selectbox(
    "Team", list(team_options), format_func=lambda rid: team_options[rid]
)
selected_roster = next(r for r in rosters if r.roster_id == selected_roster_id)

roster_rows = []
for player_id in selected_roster.players:
    player = players.get(player_id)
    if player is None:
        roster_rows.append({"Player": player_id, "Pos": "?", "Team": "?"})
        continue
    name = player.full_name or f"{player.first_name or ''} {player.last_name or ''}".strip()
    roster_rows.append(
        {
            "Player": name or player_id,
            "Pos": player.position or "?",
            "Team": player.team or "FA",
        }
    )

st.dataframe(roster_rows, hide_index=True)
