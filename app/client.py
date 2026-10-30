"""Shared, cached SleeperClient for the Streamlit app."""

from __future__ import annotations

import streamlit as st

from data import config
from data.cache import FileCache
from data.demo import DemoSleeperClient
from data.sleeper import SleeperClient


@st.cache_resource
def get_client(demo: bool = False) -> SleeperClient | DemoSleeperClient:
    if demo:
        return DemoSleeperClient()
    return SleeperClient(cache=FileCache(config.sleeper_cache_dir()))
