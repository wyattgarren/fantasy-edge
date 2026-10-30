"""Streamlit entry point: `streamlit run app/main.py`."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st  # noqa: E402

from app.client import get_client  # noqa: E402
from app.components import demo_mode, inject_theme_css  # noqa: E402
from app.state import ensure_connected, load_from_query_params, seed_demo_session_state  # noqa: E402
from data import config  # noqa: E402

st.set_page_config(page_title="fantasy-edge", page_icon=":material/sports_football:")
inject_theme_css()
load_from_query_params()
if "demo_mode" not in st.session_state:
    if st.query_params.get("demo") == "1" or config.demo_mode_default():
        seed_demo_session_state()
    else:
        st.session_state["demo_mode"] = False
ensure_connected(get_client(demo_mode()))

pg = st.navigation(
    [
        st.Page("pages/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("pages/my_team.py", title="My Team", icon=":material/person:"),
        st.Page("pages/league.py", title="League", icon=":material/groups:"),
        st.Page("pages/start_sit.py", title="Start/Sit", icon=":material/swap_horiz:"),
        st.Page("pages/waiver.py", title="Waiver Wire", icon=":material/person_add:"),
        st.Page("pages/matchup.py", title="Matchup Simulator", icon=":material/stadium:"),
        st.Page("pages/trade.py", title="Trade Analyzer", icon=":material/compare_arrows:"),
    ]
)
pg.run()
