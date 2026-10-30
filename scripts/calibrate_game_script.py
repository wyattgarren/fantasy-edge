"""Empirically derives the Vegas game-script coefficients used by
core/projection.py::game_script_adjustment, from real historical data --
NOT hand-picked. Prints fitted slopes/diagnostics to paste into source as
named constants.

Methodology: for each qualifying skill-position player-week across several
past completed seasons, compute a residual = that player's real
fantasy_points_ppr for the week minus their own season average that year
(a simple fixed-effects control isolating game-level variation from
player-quality differences). This is a one-time, offline calibration
deriving a fixed, universal constant -- not a live per-week prediction --
so using "future-relative-to-any-runtime-moment" historical data is not a
leakage problem, unlike every other no-leakage rule elsewhere in this app.

- RB residual vs. team_spread (positive = that player's team favored):
  research says spread predicts RB rushing volume specifically (favorites
  protect leads by running).
- residual vs. (total_line - NEUTRAL_TOTAL), fit separately per position:
  research says total predicts overall scoring/passing opportunity more
  generally.

Run: python scripts/calibrate_game_script.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from statistics import correlation, covariance, mean, variance

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import polars as pl  # noqa: E402

import data.stats as stats  # noqa: E402

SEASONS = [2021, 2022, 2023, 2024, 2025]
SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}
MIN_GAMES_FOR_SEASON_AVERAGE = 4  # a stable-enough season average to use as the fixed-effect baseline


def fit_slope(xs: list[float], ys: list[float]) -> tuple[float, float, int]:
    """Simple univariate OLS slope via covariance/variance (stdlib only --
    no numpy/scipy needed). Returns (slope, correlation, n)."""
    n = len(xs)
    if n < 2 or variance(xs) == 0:
        return 0.0, 0.0, n
    slope = covariance(xs, ys) / variance(xs)
    corr = correlation(xs, ys)
    return slope, corr, n


def main() -> None:
    all_total_lines: list[float] = []
    rb_spread_xy: list[tuple[float, float]] = []
    total_xy_by_position: dict[str, list[tuple[float, float]]] = {pos: [] for pos in SKILL_POSITIONS}

    for season in SEASONS:
        print(f"-- {season} --")
        weekly_stats = stats.load_weekly_stats(str(season))
        schedules = stats.load_schedules(str(season))
        all_total_lines.extend(
            t for t in schedules["total_line"].to_list() if t is not None
        )

        skill_rows = weekly_stats.filter(pl.col("position").is_in(list(SKILL_POSITIONS)))
        season_games_played = skill_rows.group_by("player_id").agg(pl.len().alias("games"))
        qualifying_ids = set(
            season_games_played.filter(pl.col("games") >= MIN_GAMES_FOR_SEASON_AVERAGE)[
                "player_id"
            ].to_list()
        )
        season_avg = (
            skill_rows.filter(pl.col("player_id").is_in(qualifying_ids))
            .group_by("player_id")
            .agg(pl.col("fantasy_points_ppr").mean().alias("season_avg_ppr"))
        )
        season_avg_by_player = dict(
            zip(season_avg["player_id"].to_list(), season_avg["season_avg_ppr"].to_list())
        )

        for row in skill_rows.filter(pl.col("player_id").is_in(qualifying_ids)).iter_rows(named=True):
            player_id, team, week, position = (
                row["player_id"],
                row["team"],
                row["week"],
                row["position"],
            )
            team_spread, total_line = stats.team_spread_and_total(schedules, team, week)
            if team_spread is None:
                continue
            residual = row["fantasy_points_ppr"] - season_avg_by_player[player_id]
            if position == "RB":
                rb_spread_xy.append((team_spread, residual))
            total_xy_by_position[position].append((total_line, residual))

    neutral_total = mean(all_total_lines)
    print(f"\nNEUTRAL_TOTAL (mean total_line across {len(all_total_lines)} games) = {neutral_total:.3f}")
    print(f"observed total_line range: {min(all_total_lines):.1f} - {max(all_total_lines):.1f}")

    spread_xs = [x for x, _ in rb_spread_xy]
    print(f"\nobserved team_spread range (RB rows): {min(spread_xs):.1f} - {max(spread_xs):.1f}")
    slope, corr, n = fit_slope(spread_xs, [y for _, y in rb_spread_xy])
    print(f"RB spread slope = {slope:.5f}  (correlation={corr:.4f}, n={n})")

    print()
    for pos in sorted(SKILL_POSITIONS):
        xy = total_xy_by_position[pos]
        xs_centered = [x - neutral_total for x, _ in xy]
        ys = [y for _, y in xy]
        slope, corr, n = fit_slope(xs_centered, ys)
        print(f"{pos} total slope = {slope:.5f}  (correlation={corr:.4f}, n={n})")


if __name__ == "__main__":
    main()
