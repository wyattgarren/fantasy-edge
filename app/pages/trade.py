import streamlit as st

from app.client import get_client
from app.components import demo_mode, page_caption
from data.exceptions import SleeperAPIError
from data.llm import explain
from data.projections import SKILL_POSITIONS
from data.trade import build_trade_evaluation

st.title("Trade Analyzer")

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
except SleeperAPIError as exc:
    st.error(f"Sleeper is unavailable right now ({exc}).")
    st.stop()

my_roster = next((r for r in rosters if r.roster_id == roster_id), None)
if my_roster is None:
    st.error("Your team wasn't found in this league anymore.")
    st.stop()

page_caption(league.name, league.season, nfl_state.week)

names_by_user_id = {u.user_id: (u.display_name or u.user_id) for u in league_users}


def player_name(player_id: str) -> str:
    player = players.get(player_id)
    if player is None:
        return player_id
    return player.full_name or f"{player.first_name or ''} {player.last_name or ''}".strip()


other_rosters = [r for r in rosters if r.roster_id != roster_id]
if not other_rosters:
    st.info("No other teams in this league to trade with.")
    st.stop()

partner_labels = {r.roster_id: names_by_user_id.get(r.owner_id, "Unclaimed team") for r in other_rosters}
partner_roster_id = st.selectbox(
    "Trade with", list(partner_labels), format_func=lambda rid: partner_labels[rid]
)
their_roster = next(r for r in rosters if r.roster_id == partner_roster_id)


def skill_players(roster) -> list[str]:
    return [
        pid
        for pid in roster.players
        if players.get(pid) is not None and players[pid].position in SKILL_POSITIONS
    ]


my_candidates = skill_players(my_roster)
their_candidates = skill_players(their_roster)

col1, col2 = st.columns(2)
gives = col1.multiselect("You give", my_candidates, format_func=player_name)
receives = col2.multiselect("You receive", their_candidates, format_func=player_name)

if not gives or not receives:
    st.info("Pick at least one player on each side to evaluate a trade.")
    st.stop()

with st.spinner("Evaluating trade from real rest-of-season values..."):
    evaluation, breakdowns = build_trade_evaluation(
        league,
        my_roster,
        their_roster,
        players,
        gives,
        receives,
        league.season,
        nfl_state.week,
        demo=demo,
    )

st.subheader("Verdict")
verdict_box = {"Accept": st.success, "Decline": st.error, "Counter": st.warning}[evaluation.verdict]
verdict_box(explain(f"**{evaluation.verdict}** — {evaluation.reason}"))

st.subheader("Before / after")
rows = [
    {
        "Side": "You",
        "ROS value change": f"{evaluation.my_result.value_change:+.1f}",
        "Lineup before": f"{evaluation.my_result.lineup_value_before:.1f}",
        "Lineup after": f"{evaluation.my_result.lineup_value_after:.1f}",
        "Lineup change": f"{evaluation.my_result.lineup_value_change:+.1f}",
    },
    {
        "Side": partner_labels[partner_roster_id],
        "ROS value change": f"{evaluation.their_result.value_change:+.1f}",
        "Lineup before": f"{evaluation.their_result.lineup_value_before:.1f}",
        "Lineup after": f"{evaluation.their_result.lineup_value_after:.1f}",
        "Lineup change": f"{evaluation.their_result.lineup_value_change:+.1f}",
    },
]
st.dataframe(rows, hide_index=True)

st.subheader("Why")
st.caption(
    "Each player's rest-of-season value: recency-weighted baseline, opportunity "
    "trend, TD/efficiency regression toward nflverse's expected-points model, "
    "average strength of remaining schedule, age-curve adjustment, and "
    "availability -- weighted across remaining games (byes excluded, playoff "
    "weeks weighted higher)."
)


def render_breakdown(column, player_id: str) -> None:
    breakdown = breakdowns.get(player_id)
    column.write(f"**{player_name(player_id)}**")
    if breakdown is None:
        column.write("—")
        return
    column.table(
        {
            "Component": list(breakdown.components),
            "Points": [f"{breakdown.components[k]:.2f}" for k in breakdown.components],
        }
    )


st.write("**You give**")
give_cols = st.columns(len(gives))
for col, pid in zip(give_cols, gives):
    render_breakdown(col, pid)

st.write("**You receive**")
receive_cols = st.columns(len(receives))
for col, pid in zip(receive_cols, receives):
    render_breakdown(col, pid)
