"""Turns a raw stat line into fantasy points using a league's scoring_settings."""

from __future__ import annotations


def score_stat_line(stats: dict[str, float], scoring_settings: dict[str, float]) -> float:
    total = sum(value * scoring_settings.get(stat, 0.0) for stat, value in stats.items())
    return round(total, 2)
