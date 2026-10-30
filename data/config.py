"""Env-var configuration, read live (never cached at import time) so tests
can monkeypatch.setenv per-test. `.env` is loaded once at import if present;
every real deployment (CI, Streamlit Cloud) sets env vars natively instead.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

TRUTHY = {"1", "true", "yes"}


def llm_provider() -> str:
    return os.environ.get("LLM_PROVIDER", "").lower()


def ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def ollama_model() -> str:
    return os.environ.get("OLLAMA_MODEL", "llama3.2")


def ollama_timeout_seconds() -> float:
    # Generous default: a cold-start model load on a typical local machine
    # can take several seconds (confirmed ~5.5s for a 3B model); after the
    # first call per session Ollama keeps it warm, so this only costs real
    # time once per page per Ollama restart.
    return float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "8"))


def demo_mode_default() -> bool:
    return os.environ.get("DEMO_MODE", "").lower() in TRUTHY


def sleeper_cache_dir() -> str:
    return os.environ.get("SLEEPER_CACHE_DIR", ".cache")
