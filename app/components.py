"""Small bits shared by every page."""

from __future__ import annotations

import streamlit as st

_THEME_CSS = """
<style>
/* Page background: pale silver/steel wash */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #F6F8FB 0%, #ECF0F5 45%, #E4E9F0 100%);
}

/* Top header bar: frosted glass strip */
[data-testid="stHeader"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.65) 0%, rgba(255,255,255,0.15) 100%);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(255,255,255,0.5);
}

/* Nav rail: glass panel */
[data-testid="stSidebar"] {
    background: linear-gradient(160deg, rgba(255,255,255,0.55) 0%, rgba(230,234,240,0.35) 100%);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    box-shadow: 4px 0 24px rgba(20,23,31,0.06);
}

/* Headings: metallic gradient trim */
h1, h2, h3 { padding-bottom: 0.35rem; position: relative; }
h1::after, h2::after, h3::after {
    content: ""; display: block; width: 64px; height: 3px;
    margin-top: 0.3rem; border-radius: 2px;
    background: linear-gradient(90deg, #AEB8C4 0%, #FFFFFF 30%, #155EEF 60%, #FFFFFF 85%, #AEB8C4 100%);
}

/* Metric tiles: glass panel */
[data-testid="stMetric"] {
    background: linear-gradient(145deg, rgba(255,255,255,0.75) 0%, rgba(255,255,255,0.35) 100%);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.6);
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(20,30,50,0.10), inset 0 1px 0 rgba(255,255,255,0.8);
    padding: 1rem 1.1rem;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 28px rgba(20,30,50,0.14), inset 0 1px 0 rgba(255,255,255,0.9);
}

/* Expanders: glass body + metallic sheen header */
[data-testid="stExpander"] {
    background: linear-gradient(145deg, rgba(255,255,255,0.7) 0%, rgba(255,255,255,0.3) 100%);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.6);
    border-radius: 16px;
    box-shadow: 0 6px 20px rgba(20,30,50,0.08);
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    background: linear-gradient(90deg, #EDEFF3 0%, #FFFFFF 35%, #DDE2E8 100%);
}
[data-testid="stExpander"] summary:hover {
    background: linear-gradient(90deg, #E4E8EE 0%, #FFFFFF 35%, #D3D9E1 100%);
}

/* Dataframe/table outer frame only -- stDataFrame's grid is canvas-rendered
   (glide-data-grid), so its header/cells can ONLY be themed via the
   dataframeHeaderBackgroundColor/dataframeHeaderTextColor/dataframeBorderColor
   keys in .streamlit/config.toml, never CSS. stTable renders real HTML, so
   its header gradient below works normally. */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(20,30,50,0.08);
    border: 1px solid #C9CFD8;
}
[data-testid="stTableStyledTable"] thead tr th {
    background: linear-gradient(180deg, #F3F5F8 0%, #E2E6EC 100%);
}

/* Buttons: glossy capsules */
[data-testid^="stBaseButton-primary"] {
    background: linear-gradient(180deg, #2E78FF 0%, #155EEF 55%, #0C3FC2 100%);
    color: #FFFFFF;
    border: 1px solid rgba(255,255,255,0.35);
    box-shadow: 0 4px 14px rgba(21,94,239,0.35), inset 0 1px 0 rgba(255,255,255,0.5);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
[data-testid^="stBaseButton-primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(21,94,239,0.45), inset 0 1px 0 rgba(255,255,255,0.6);
}
[data-testid^="stBaseButton-primary"]:active {
    transform: translateY(0);
    box-shadow: 0 2px 8px rgba(21,94,239,0.35), inset 0 1px 0 rgba(255,255,255,0.4);
}
[data-testid^="stBaseButton-secondary"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #E7EBF0 60%, #D3D9E1 100%);
    color: #15181F;
    border: 1px solid rgba(255,255,255,0.8);
    box-shadow: 0 2px 8px rgba(20,30,50,0.10), inset 0 1px 0 rgba(255,255,255,0.9);
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
[data-testid^="stBaseButton-secondary"]:hover {
    background: linear-gradient(180deg, #FFFFFF 0%, #EEF1F5 60%, #DADFE6 100%);
    transform: translateY(-1px);
}
</style>
"""


def inject_theme_css() -> None:
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def demo_mode() -> bool:
    return bool(st.session_state.get("demo_mode"))


def page_caption(league_name: str, season: str, week: int | None = None) -> None:
    if demo_mode():
        st.caption("🎮 Demo mode — sample data, no Sleeper account needed.")
    suffix = f", week {week}" if week is not None else ""
    st.caption(f"{league_name.strip()} · {season} season{suffix}")
