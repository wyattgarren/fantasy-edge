"""Small bits shared by every page."""

from __future__ import annotations

import streamlit as st


def demo_mode() -> bool:
    return bool(st.session_state.get("demo_mode"))


def page_caption(league_name: str, season: str, week: int | None = None) -> None:
    if demo_mode():
        st.caption("🎮 Demo mode — sample data, no Sleeper account needed.")
    suffix = f", week {week}" if week is not None else ""
    st.caption(f"{league_name.strip()} · {season} season{suffix}")
