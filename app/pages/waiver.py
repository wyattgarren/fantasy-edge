import streamlit as st

from app.client import get_client
from app.components import demo_mode, page_caption
from data.exceptions import SleeperAPIError
from data.llm import explain
from data.waiver import build_waiver_board

st.title("Waiver Wire")

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
    players = client.get_players()
    nfl_state = client.get_nfl_state()
except SleeperAPIError as exc:
    st.error(f"Sleeper is unavailable right now ({exc}).")
    st.stop()

my_roster = next((r for r in rosters if r.roster_id == roster_id), None)
if my_roster is None:
    st.error("Your team wasn't found in this league anymore.")
    st.stop()

page_caption(league.name, league.season, nfl_state.week)

is_faab = float(league.settings.get("waiver_budget") or 0) > 0
if is_faab:
    budget = float(league.settings.get("waiver_budget") or 0)
    used = float(my_roster.settings.get("waiver_budget_used") or 0)
    st.caption(f"FAAB budget remaining: **{budget - used:.0f}** of {budget:.0f}")
else:
    position = my_roster.settings.get("waiver_position")
    st.caption(f"Waiver priority league (not FAAB)." + (f" Your priority: **{position}**" if position else ""))


def player_name(player_id: str | None) -> str:
    if player_id is None:
        return "—"
    player = players.get(player_id)
    if player is None:
        return player_id
    return player.full_name or f"{player.first_name or ''} {player.last_name or ''}".strip()


with st.spinner("Ranking free agents from real stats..."):
    targets, pool_size = build_waiver_board(
        client, league, rosters, my_roster, players, league.season, nfl_state.week, demo=demo
    )

st.subheader("Verdict")
if not targets:
    st.info("No relevant free agents found (no active skill-position players with recorded stats this season).")
else:
    top = targets[0]
    parts = [f"Top add: **{player_name(top.player_id)}** (+{top.ros_value:.1f} ROS pts)"]
    if top.suggested_drop_player_id:
        parts.append(f"drop **{player_name(top.suggested_drop_player_id)}**")
    if top.bid_low is not None and top.bid_high is not None:
        parts.append(f"bid **{top.bid_low:.0f}-{top.bid_high:.0f}%**")
    st.success(explain(", ".join(parts)))

    st.subheader("Targets")
    st.caption(f"Showing top {min(50, len(targets))} of {pool_size} relevant free agents (ranked by score).")
    rows = []
    for t in targets[:50]:
        player = players.get(t.player_id)
        rows.append(
            {
                "Player": player_name(t.player_id),
                "Pos": player.position if player else "?",
                "Team": player.team if player and player.team else "FA",
                "ROS pts": f"{t.ros_value:.1f}",
                "Need": f"{t.need_bonus:.1f}",
                "Trending": f"{t.trending_bonus:.1f}",
                "Score": f"{t.score:.1f}",
                "Suggested drop": player_name(t.suggested_drop_player_id),
                "Bid %": f"{t.bid_low:.0f}-{t.bid_high:.0f}%" if t.bid_low is not None else "—",
            }
        )
    st.dataframe(rows, hide_index=True)
