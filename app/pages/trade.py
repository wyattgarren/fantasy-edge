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

trade_deadline = league.settings.get("trade_deadline")
if trade_deadline:
    if nfl_state.week >= int(trade_deadline):
        st.warning(f"The trade deadline (week {int(trade_deadline)}) has passed.")
    else:
        st.caption(f"Trade deadline: week {int(trade_deadline)}.")

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
    evaluation, breakdowns, vorp, handcuff_warnings = build_trade_evaluation(
        league,
        rosters,
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

for warning in handcuff_warnings.get("you", []):
    st.warning(f"You'd be {warning}.")
for warning in handcuff_warnings.get("them", []):
    st.warning(f"{partner_labels[partner_roster_id]} would be {warning}.")

my_vorp_change = sum(vorp.get(pid, 0.0) for pid in receives) - sum(vorp.get(pid, 0.0) for pid in gives)
their_vorp_change = -my_vorp_change

st.subheader("Before / after")
rows = [
    {
        "Side": "You",
        "ROS value change": f"{evaluation.my_result.value_change:+.1f}",
        "VORP change": f"{my_vorp_change:+.1f}",
        "Lineup before": f"{evaluation.my_result.lineup_value_before:.1f}",
        "Lineup after": f"{evaluation.my_result.lineup_value_after:.1f}",
        "Lineup change": f"{evaluation.my_result.lineup_value_change:+.1f}",
    },
    {
        "Side": partner_labels[partner_roster_id],
        "ROS value change": f"{evaluation.their_result.value_change:+.1f}",
        "VORP change": f"{their_vorp_change:+.1f}",
        "Lineup before": f"{evaluation.their_result.lineup_value_before:.1f}",
        "Lineup after": f"{evaluation.their_result.lineup_value_after:.1f}",
        "Lineup change": f"{evaluation.their_result.lineup_value_change:+.1f}",
    },
]
st.dataframe(rows, hide_index=True)
st.caption(
    "VORP change: positional-scarcity-adjusted value swing -- positive means you're gaining more "
    "surplus over a replacement-level player at that position than you're giving up."
)

FACTOR_LABELS: dict[str, str] = {
    "baseline": "Recent scoring",
    "opportunity": "Role trend",
    "regression": "TD luck adjustment",
    "matchup_adjustment": "Schedule strength",
    "game_script_adjustment": "Vegas game script",
    "red_zone_adjustment": "Red zone role",
    "age_multiplier": "Age factor",
    "availability_multiplier": "Health status",
    "per_game": "Projected per game",
    "games_weight": "Weighted games left",
    "vorp": "Positional value (VORP)",
}

FACTOR_EXPLANATIONS: dict[str, str] = {
    "baseline": "How many points they've scored per game recently, weighted toward their most recent games.",
    "opportunity": "Whether their share of their team's targets, carries, and snaps is trending up or down.",
    "regression": (
        "Nudges scoring back toward what their usage and efficiency should produce, "
        "correcting for touchdown or big-play luck that tends to even out over time."
    ),
    "matchup_adjustment": "How tough their remaining opponents are, on average, compared to a typical schedule.",
    "game_script_adjustment": (
        "A small, data-calibrated nudge from real Vegas point spreads and totals -- favorites tend "
        "to run more, and higher-scoring games mean more opportunity for everyone."
    ),
    "red_zone_adjustment": (
        "Whether their share of their team's goal-line carries/targets -- the real touches that "
        "turn into touchdowns -- is trending up or down."
    ),
    "age_multiplier": "A discount for players at an age when their position historically starts to decline.",
    "availability_multiplier": (
        "A discount applied only to their very next game if they're currently banged up, "
        "based on their current injury tag."
    ),
    "per_game": "The final per-game rate after combining all the factors above.",
    "games_weight": "How many games remain this season, with byes removed and the fantasy playoffs counted extra.",
    "vorp": (
        "Value over a replacement-level player at the same position in a league this size -- "
        "a QB means something very different in a 1-QB league than a superflex one, and this "
        "accounts for that instead of just comparing raw point totals."
    ),
}

st.subheader("Why")
with st.expander("What goes into this number?"):
    st.table(
        {
            "Factor": [FACTOR_LABELS[k] for k in FACTOR_LABELS],
            "What it means": [FACTOR_EXPLANATIONS[k] for k in FACTOR_LABELS],
        }
    )
    st.caption("Rest-of-season total = Projected per game × Weighted games left.")


# Sleeper encodes WR sub-slots as LWR/RWR/SWR (left/right/slot), never the
# literal "WR" -- see data/models.py::Player.depth_chart_position.
_WR_SLOT_NAMES = {"LWR": "left", "RWR": "right", "SWR": "slot"}


def depth_chart_label(player) -> str | None:
    if player.depth_chart_order is None or player.depth_chart_position is None:
        return None
    slot = _WR_SLOT_NAMES.get(player.depth_chart_position)
    if slot is not None:
        return f"WR{player.depth_chart_order} ({slot})"
    return f"{player.depth_chart_position}{player.depth_chart_order}"


def render_breakdown(column, player_id: str) -> None:
    breakdown = breakdowns.get(player_id)
    player = players.get(player_id)
    column.write(f"**{player_name(player_id)}**")
    if breakdown is None:
        column.write("—")
        return

    status = (player.injury_status or player.status or "Active") if player else "Unknown"

    column.metric(
        "Rest-of-season value",
        f"{breakdown.total:.1f} pts",
        help=(
            f"{breakdown.per_game:.1f} pts/gm projected × "
            f"{breakdown.games_weight:.1f} weighted games left."
        ),
    )
    if player is not None:
        depth_label = depth_chart_label(player)
        identity = f"{player.position} · {player.team} · {status}"
        if depth_label:
            identity += f" · {depth_label}"
        column.write(identity)

    rows = [
        ("Recent scoring", f"{breakdown.baseline:.1f} pts/gm"),
        ("Role trend", f"{breakdown.opportunity:+.1f} pts/gm"),
        ("TD luck adjustment", f"{breakdown.regression:+.1f} pts/gm"),
        ("Schedule strength", f"{breakdown.avg_matchup_adjustment:+.1f} pts/gm"),
        ("Vegas game script", f"{breakdown.avg_game_script_adjustment:+.1f} pts/gm"),
        ("Red zone role", f"{breakdown.red_zone_adjustment:+.1f} pts/gm"),
        ("Age factor", f"{breakdown.age_multiplier:.0%}"),
        ("Health status", f"{breakdown.availability_multiplier:.0%} ({status})"),
        ("Projected per game", f"{breakdown.per_game:.1f} pts/gm"),
        ("Weighted games left", f"{breakdown.games_weight:.1f} games"),
        ("Positional value (VORP)", f"{vorp.get(player_id, 0.0):+.1f} pts"),
    ]
    column.table({"Factor": [r[0] for r in rows], "Value": [r[1] for r in rows]})


st.write("**You give**")
give_cols = st.columns(len(gives))
for col, pid in zip(give_cols, gives):
    render_breakdown(col, pid)

st.write("**You receive**")
receive_cols = st.columns(len(receives))
for col, pid in zip(receive_cols, receives):
    render_breakdown(col, pid)
