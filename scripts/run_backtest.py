"""Runs the Phase 2 backtest against the connected league's real season data
and prints a markdown MAE table (model vs. two naive baselines) for the
README.

Only includes players with a full, gap-free game log through the last
completed week ("iron man" filter) -- this keeps each player's week index
aligned with calendar week (needed to look up their real opponent/
opportunity history per week) without having to model bye/missed weeks.

Run: python scripts/run_backtest.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from statistics import mean

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import polars as pl

import data.stats as stats
from core.backtest import BacktestResult, PlayerSeries, backtest
from core.projection import project_player
from data.cache import FileCache
from data.sleeper import SleeperClient

LEAGUE_ID = "1391465605172834304"
SEASON = "2026"


def make_predict_fn(
    position: str,
    opponent_by_week: dict[int, str],
    share_by_week: dict[int, float],
    points_allowed: pl.DataFrame,
):
    def predict(prior: list[float], player: PlayerSeries) -> float:
        week = len(prior) + 1
        prior_weeks = list(range(1, week))
        recent_weeks = prior_weeks[-3:]
        recent_share = mean(share_by_week[w] for w in recent_weeks)
        season_share = mean(share_by_week[w] for w in prior_weeks)

        opponent = opponent_by_week[week]
        opp_allowed = stats.points_allowed_through_week(points_allowed, opponent, position, week)
        league_avg = stats.league_avg_points_allowed_through_week(points_allowed, position, week)
        if opp_allowed is None or league_avg is None:
            opp_allowed = league_avg = 0.0

        projection = project_player(
            weekly_points=prior,
            recent_share=recent_share,
            season_share=season_share,
            opponent_points_allowed=opp_allowed,
            league_avg_points_allowed=league_avg,
            weeks_played=len(prior),
            status="Active",  # iron-man filter guarantees they played every week
        )
        return projection.mean

    return predict


def build_player_series(
    weekly_points, opportunity, points_allowed, last_completed_week: int
) -> tuple[list[PlayerSeries], dict[str, pl.DataFrame]]:
    series_list: list[PlayerSeries] = []
    predict_fns = {}

    grouped = weekly_points.sort("week").group_by(
        ["player_id", "player_display_name", "position", "team"], maintain_order=True
    )
    for (player_id, display_name, position, team), rows in grouped:
        weeks = rows["week"].to_list()
        if weeks != list(range(1, last_completed_week + 1)):
            continue  # skip anyone with a bye/missed week in range

        fantasy_points = rows["fantasy_points"].to_list()
        opponent_by_week = dict(zip(weeks, rows["opponent_team"].to_list()))

        opp_rows = opportunity.filter(opportunity["player_id"] == player_id).sort("week")
        share_by_week = dict(
            zip(opp_rows["week"].to_list(), opp_rows["opportunity_share"].to_list())
        )
        if set(weeks) - set(share_by_week):
            continue  # missing opportunity data for some week in range

        series_list.append(
            PlayerSeries(position=position, weekly_points=fantasy_points, player_id=player_id)
        )
        predict_fns[player_id] = make_predict_fn(
            position, opponent_by_week, share_by_week, points_allowed
        )

    return series_list, predict_fns


def dispatching_predict_fn(predict_fns):
    def predict(prior, player):
        return predict_fns[player.player_id](prior, player)

    return predict


def print_markdown_table(result: BacktestResult) -> None:
    positions = sorted(result.model_mae_by_position)
    print(f"Weeks tested: {result.weeks_tested}\n")
    print("| Position | Model MAE | Season-avg baseline MAE | Last-week baseline MAE |")
    print("|---|---|---|---|")
    for pos in positions:
        print(
            f"| {pos} | {result.model_mae_by_position[pos]} "
            f"| {result.season_avg_mae_by_position[pos]} "
            f"| {result.last_week_mae_by_position[pos]} |"
        )


def main() -> None:
    client = SleeperClient(cache=FileCache(".cache"))
    league = client.get_league(LEAGUE_ID)
    nfl_state = client.get_nfl_state()
    scoring_settings = league.scoring_settings

    last_completed_week = nfl_state.week - 1
    print(
        f"Connected league: {league.name.strip()} ({SEASON})\n"
        f"Current week: {nfl_state.week} -> backtesting weeks 2-{last_completed_week}\n"
    )

    weekly_stats = stats.load_weekly_stats(SEASON)
    weekly_points = stats.weekly_fantasy_points(weekly_stats, scoring_settings)
    points_allowed = stats.points_allowed_by_position(weekly_points)
    snap_counts = stats.load_snap_counts(SEASON)
    id_map = stats.load_player_id_map()
    opportunity = stats.opportunity_shares(weekly_stats, snap_counts, id_map)

    players, predict_fns = build_player_series(
        weekly_points, opportunity, points_allowed, last_completed_week
    )
    print(f"Players with a full {last_completed_week}-week history: {len(players)}\n")

    result = backtest(
        players,
        start_week=2,
        end_week=last_completed_week,
        predict_fn=dispatching_predict_fn(predict_fns),
    )
    print_markdown_table(result)


if __name__ == "__main__":
    main()
