"""Shared, cached SleeperClient for the Streamlit app."""

from __future__ import annotations

import streamlit as st

from data.cache import FileCache
from data.sleeper import SleeperClient


@st.cache_resource
def get_client() -> SleeperClient:
    return SleeperClient(cache=FileCache(".cache"))
