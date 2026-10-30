"""Optional, local-only AI gloss on top of already-computed verdicts.

Ground rule (see docs/ROADMAP.md): the LLM may only rephrase numbers that
core/ and data/ already computed. It never invents a stat, and the app must
work identically with no LLM configured -- `explain()` always has a plain
template sentence to fall back to.
"""

from __future__ import annotations

import httpx

from data import config

SYSTEM_PROMPT = (
    "You are rephrasing a fantasy football recommendation for a friendly, "
    "casual app. Restate the given sentence in 2-3 short, conversational "
    "sentences. Keep the same verdict and every number/player name exactly "
    "as given. Never introduce a stat, player, or number that isn't already "
    "in the input."
)


def explain(template_sentence: str) -> str:
    """Returns an LLM-polished version of `template_sentence`, or the
    template itself, unchanged, if no LLM is configured or anything about
    the call fails (down, slow, malformed response, etc.)."""
    if config.llm_provider() != "ollama":
        return template_sentence

    try:
        response = httpx.post(
            f"{config.ollama_host()}/api/generate",
            json={
                "model": config.ollama_model(),
                "system": SYSTEM_PROMPT,
                "prompt": template_sentence,
                "stream": False,
            },
            timeout=config.ollama_timeout_seconds(),
        )
        response.raise_for_status()
        text = response.json().get("response", "").strip()
    except Exception:
        return template_sentence

    return text or template_sentence
