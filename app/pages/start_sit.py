import streamlit as st

from app.client import get_client
from core.lineup import lineup_value, optimal_lineup
from data.exceptions import SleeperAPIError
from data.projections import opponent_this_week, project_roster_week
import data.stats as stats

st.title("Start/Sit")

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
    players = client.get_players()
    nfl_state = client.get_nfl_state()
except SleeperAPIError as exc:
    st.error(f"Sleeper is unavailable right now ({exc}).")
    st.stop()

my_roster = next((r for r in rosters if r.roster_id == roster_id), None)
if my_roster is None:
    st.error("Your team wasn't found in this league anymore.")
    st.stop()

st.caption(f"{league.name.strip()} · {league.season} season, week {nfl_state.week}")

with st.spinner("Computing projections from real stats..."):
    projections = project_roster_week(league, my_roster, players, league.season, nfl_state.week)
    schedules = stats.load_schedules(league.season)

if not projections:
    st.info("No skill-position (QB/RB/WR/TE) players with projections were found on this roster.")
    st.stop()

risk = st.slider(
    "Risk mode", 0.0, 1.0, 0.5, help="0.0 = Safe (rank by floor), 1.0 = Upside (rank by ceiling)"
)
st.caption("Safe (floor) ←――――――――――→ Upside (ceiling)")

player_positions = {pid: players[pid].position for pid in projections}
optimal = optimal_lineup(league.roster_positions, player_positions, projections, risk=risk)

starter_slots = [pos for pos in league.roster_positions if pos != "BN"]


def player_name(player_id: str | None) -> str:
    if player_id is None:
        return "—"
    player = players.get(player_id)
    if player is None:
        return player_id
    return player.full_name or f"{player.first_name or ''} {player.last_name or ''}".strip()


st.subheader("Verdict")
changes = []
for slot, current_pid, assignment in zip(starter_slots, my_roster.starters, optimal.assignments):
    recommended_pid = assignment.player_id
    if recommended_pid is None or recommended_pid == current_pid:
        continue
    if current_pid not in projections:
        continue  # not a skill-position player we project (e.g. already empty slot)
    delta = lineup_value(projections[recommended_pid], risk) - lineup_value(
        projections[current_pid], risk
    )
    if delta > 0:
        changes.append((slot, recommended_pid, current_pid, delta))

if not changes:
    st.success("Your current lineup is already optimal at this risk level.")
else:
    lines = "\n".join(
        f"- **{slot}**: start **{player_name(rec)}** over {player_name(cur)} (+{delta:.1f} pts)"
        for slot, rec, cur, delta in changes
    )
    verb_phrase = "Make this 1 change" if len(changes) == 1 else f"Make these {len(changes)} changes"
    st.info(f"{verb_phrase}:\n\n{lines}")

st.subheader("Recommended lineup")
rows = []
for slot, current_pid, assignment in zip(starter_slots, my_roster.starters, optimal.assignments):
    recommended_pid = assignment.player_id or current_pid
    proj = projections.get(recommended_pid)
    rows.append(
        {
            "Slot": slot,
            "Recommended": player_name(recommended_pid)
            + (" (not modeled)" if assignment.player_id is None else ""),
            "Mean": f"{proj.mean:.1f}" if proj else "—",
            "Floor": f"{proj.floor:.1f}" if proj else "—",
            "Ceiling": f"{proj.ceiling:.1f}" if proj else "—",
            "Current starter": player_name(current_pid),
        }
    )
st.dataframe(rows, hide_index=True)

st.subheader("Compare two players")
player_ids = sorted(projections, key=lambda pid: player_name(pid))
col1, col2 = st.columns(2)
left_pid = col1.selectbox("Player A", player_ids, format_func=player_name, key="compare_a")
right_pid = col2.selectbox(
    "Player B",
    player_ids,
    index=min(1, len(player_ids) - 1),
    format_func=player_name,
    key="compare_b",
)


def render_player_card(column, player_id: str) -> None:
    proj = projections[player_id]
    player = players[player_id]
    opponent = opponent_this_week(schedules, player.team, nfl_state.week)
    column.metric(player_name(player_id), f"{proj.mean:.1f} pts")
    column.write(f"Floor **{proj.floor:.1f}** · Ceiling **{proj.ceiling:.1f}** · Std {proj.std:.1f}")
    column.write(f"{player.position} · {player.team} · vs. {opponent or 'BYE'}")
    column.write(f"Status: {player.injury_status or player.status or 'Active'}")
    column.table(
        {
            "Component": list(proj.components),
            "Points": [f"{proj.components[k]:.2f}" for k in proj.components],
        }
    )


render_player_card(col1, left_pid)
render_player_card(col2, right_pid)
