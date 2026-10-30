import streamlit as st

from app.client import get_client
from app.components import demo_mode, page_caption
from data.exceptions import SleeperAPIError
from data.llm import explain
from data.simulate import build_matchup_simulation

st.title("Matchup Simulator")

if not st.session_state.get("league_id") or not st.session_state.get("roster_id"):
    st.info("Connect a league on the Home page first.")
    if st.button("Go to Home"):
        st.switch_page("pages/home.py")
    st.stop()

demo = demo_mode()
client = get_client(demo)
league_id = st.session_state["league_id"]
roster_id = st.session_state["roster_id"]

try:
    league = client.get_league(league_id)
    rosters = client.get_rosters(league_id)
    league_users = client.get_league_users(league_id)
    players = client.get_players()
    nfl_state = client.get_nfl_state()
    matchups = client.get_matchups(league_id, nfl_state.week)
except SleeperAPIError as exc:
    st.error(f"Sleeper is unavailable right now ({exc}).")
    st.stop()

my_roster = next((r for r in rosters if r.roster_id == roster_id), None)
if my_roster is None:
    st.error("Your team wasn't found in this league anymore.")
    st.stop()

page_caption(league.name, league.season, nfl_state.week)

my_matchup = next((m for m in matchups if m.roster_id == roster_id), None)
opponent_matchup = (
    next(
        (m for m in matchups if m.matchup_id == my_matchup.matchup_id and m.roster_id != roster_id),
        None,
    )
    if my_matchup is not None and my_matchup.matchup_id is not None
    else None
)
if opponent_matchup is None:
    st.info("No matchup found for this week.")
    st.stop()

opponent_roster = next((r for r in rosters if r.roster_id == opponent_matchup.roster_id), None)
if opponent_roster is None:
    st.error("Your opponent's roster wasn't found.")
    st.stop()

names_by_user_id = {u.user_id: (u.display_name or u.user_id) for u in league_users}
opponent_name = names_by_user_id.get(opponent_roster.owner_id, "Unknown team")


def player_name(player_id: str) -> str:
    player = players.get(player_id)
    if player is None:
        return player_id
    return player.full_name or f"{player.first_name or ''} {player.last_name or ''}".strip()


with st.spinner(f"Running 10,000 simulations vs. {opponent_name}..."):
    result = build_matchup_simulation(
        league, my_roster, opponent_roster, players, league.season, nfl_state.week, demo=demo
    )

st.caption("K/DEF aren't modeled (see Phase 2/3) and are excluded from the simulation.")

st.subheader("Verdict")
col1, col2, col3 = st.columns(3)
col1.metric("Win probability", f"{result.win_probability * 100:.0f}%")
col2.metric("Projected score", f"{result.my_mean:.1f} - {result.opponent_mean:.1f}")
col3.metric("Score range", f"{result.my_floor:.1f} - {result.my_ceiling:.1f}")

if result.swing_players:
    top_pid, top_swing = result.swing_players[0]
    verdict_sentence = (
        f"You're a {result.win_probability * 100:.0f}% favorite, projected "
        f"{result.my_mean:.1f}-{result.opponent_mean:.1f} vs. {opponent_name}. "
        f"**{player_name(top_pid)}** swings this matchup the most ({top_swing:+.1f} pts "
        "between your wins and losses) -- worth watching closely."
    )
    st.info(explain(verdict_sentence))

st.subheader("Who swings this matchup")
st.caption(
    "How much higher each player's simulated score was in your wins vs. your losses -- "
    "the biggest gap is the player most worth watching."
)
rows = [
    {"Player": player_name(pid), "Swing (pts)": f"{swing:+.2f}"}
    for pid, swing in result.swing_players
]
st.dataframe(rows, hide_index=True)
