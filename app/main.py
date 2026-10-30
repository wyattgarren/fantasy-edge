"""Streamlit entry point: `streamlit run app/main.py`."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st  # noqa: E402

from app.client import get_client  # noqa: E402
from app.state import ensure_connected, load_from_query_params  # noqa: E402

st.set_page_config(page_title="fantasy-edge", page_icon=":material/sports_football:")
load_from_query_params()
ensure_connected(get_client())

pg = st.navigation(
    [
        st.Page("pages/home.py", title="Home", icon=":material/home:", default=True),
        st.Page("pages/my_team.py", title="My Team", icon=":material/person:"),
        st.Page("pages/league.py", title="League", icon=":material/groups:"),
        st.Page("pages/start_sit.py", title="Start/Sit", icon=":material/swap_horiz:"),
        st.Page("pages/waiver.py", title="Waiver Wire", icon=":material/person_add:"),
    ]
)
pg.run()
