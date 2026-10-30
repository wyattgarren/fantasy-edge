import streamlit as st

from app.client import get_client
from data.exceptions import SleeperAPIError

st.title("My Team")

if not st.session_state.get("league_id") or not st.session_state.get("roster_id"):
    st.info("Connect a league on the Home page first.")
    if st.button("Go to Home"):
        st.switch_page("pages/home.py")
    st.stop()

client = get_client()
league_id = st.session_state["league_id"]
roster_id = st.session_state["roster_id"]

try:
    league = client.get_league(league_id)
    rosters = client.get_rosters(league_id)
    league_users = client.get_league_users(league_id)
    nfl_state = client.get_nfl_state()
    matchups = client.get_matchups(league_id, nfl_state.week)
    players = client.get_players()
except SleeperAPIError as exc:
    st.error(f"Sleeper is unavailable right now ({exc}).")
    st.stop()

my_roster = next((r for r in rosters if r.roster_id == roster_id), None)
if my_roster is None:
    st.error("Your team wasn't found in this league anymore.")
    st.stop()

names_by_user_id = {u.user_id: (u.display_name or u.user_id) for u in league_users}
st.caption(f"{league.name.strip()} · {league.season} season, week {nfl_state.week}")


def player_row(player_id: str, slot: str) -> dict[str, str]:
    player = players.get(player_id)
    if player is None:
        return {"Slot": slot, "Player": player_id, "Pos": "?", "Team": "?", "Status": "?", "Bye": "-"}
    name = player.full_name or f"{player.first_name or ''} {player.last_name or ''}".strip()
    return {
        "Slot": slot,
        "Player": name or player_id,
        "Pos": player.position or "?",
        "Team": player.team or "FA",
        "Status": player.injury_status or player.status or "Active",
        "Bye": "-",  # bye weeks arrive with nflreadpy schedule data in Phase 2
    }


starter_slots = [pos for pos in league.roster_positions if pos != "BN"]
starters_rows = [
    player_row(player_id, slot) for slot, player_id in zip(starter_slots, my_roster.starters)
]

reserve_ids = set(my_roster.reserve or [])
bench_ids = [
    p for p in my_roster.players if p not in my_roster.starters and p not in reserve_ids
]
bench_rows = [player_row(pid, "BN") for pid in bench_ids]
reserve_rows = [player_row(pid, "IR") for pid in reserve_ids]

st.subheader("Starters")
st.dataframe(starters_rows, hide_index=True)

st.subheader("Bench")
st.dataframe(bench_rows, hide_index=True)

if reserve_rows:
    st.subheader("Reserve / IR")
    st.dataframe(reserve_rows, hide_index=True)

st.subheader("This week's opponent")
my_matchup = next((m for m in matchups if m.roster_id == roster_id), None)
opponent_matchup = (
    next(
        (
            m
            for m in matchups
            if m.matchup_id == my_matchup.matchup_id and m.roster_id != roster_id
        ),
        None,
    )
    if my_matchup is not None and my_matchup.matchup_id is not None
    else None
)

if opponent_matchup is None:
    st.info("No matchup found for this week.")
else:
    opponent_roster = next(
        (r for r in rosters if r.roster_id == opponent_matchup.roster_id), None
    )
    opponent_name = (
        names_by_user_id.get(opponent_roster.owner_id, "Unknown team")
        if opponent_roster
        else "Unknown team"
    )
    st.metric(label=f"vs. {opponent_name}", value=f"{my_matchup.points:.1f} - {opponent_matchup.points:.1f}")
