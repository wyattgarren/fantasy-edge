"""Weekly player stats, snap counts, schedules, and the player-ID crosswalk,
via nflreadpy. All nflreadpy/polars/ID-crosswalk/team-code integration lives
here -- core/projection.py and core/backtest.py only ever see plain numbers.
"""

from __future__ import annotations

from pathlib import Path
from statistics import mean

import nflreadpy as nfl
import polars as pl

from core.scoring import score_stat_line

nfl.config.update_config(
    cache_mode="filesystem",
    cache_dir=Path(".cache/nflreadpy"),
    cache_duration=24 * 60 * 60,
)

DEMO_DATA_DIR = Path(__file__).resolve().parent / "demo_data" / "stats"

# nflverse uses "LA" for the Rams; Sleeper uses "LAR". Every other team code
# matches between the two (confirmed against the real 2026 schedule/rosters).
TEAM_CODE_FIXES = {"LA": "LAR"}

# nflverse player-stats column -> Sleeper scoring_settings key. Covers the
# skill-position (QB/RB/WR/TE) stats a standard scoring_settings scores on.
# K/DEF fantasy points aren't computed here -- DEF scoring is a team-level
# stat (points allowed, sacks, turnovers) nflreadpy's player_stats doesn't
# carry, and K needs a much more granular FG-distance mapping; out of scope
# for Phase 2.
STAT_KEY_MAP = {
    "completions": "pass_cmp",
    "attempts": "pass_att",
    "passing_yards": "pass_yd",
    "passing_tds": "pass_td",
    "passing_interceptions": "pass_int",
    "passing_2pt_conversions": "pass_2pt",
    "passing_first_downs": "pass_fd",
    "carries": "rush_att",
    "rushing_yards": "rush_yd",
    "rushing_tds": "rush_td",
    "rushing_2pt_conversions": "rush_2pt",
    "rushing_first_downs": "rush_fd",
    "receptions": "rec",
    "receiving_yards": "rec_yd",
    "receiving_tds": "rec_td",
    "receiving_2pt_conversions": "rec_2pt",
    "receiving_first_downs": "rec_fd",
}

SKILL_POSITIONS = ["QB", "RB", "WR", "TE"]


def _fix_team_codes(df: pl.DataFrame, *columns: str) -> pl.DataFrame:
    for col in columns:
        df = df.with_columns(pl.col(col).replace(TEAM_CODE_FIXES))
    return df


def load_player_id_map(demo: bool = False) -> pl.DataFrame:
    """sleeper_id <-> gsis_id (player_stats) <-> pfr_id (snap_counts)."""
    if demo:
        return pl.read_parquet(DEMO_DATA_DIR / "player_ids.parquet")
    ids = nfl.load_ff_playerids()
    return (
        ids.select(["sleeper_id", "gsis_id", "pfr_id", "name"])
        .filter(pl.col("sleeper_id").is_not_null())
        .with_columns(pl.col("sleeper_id").cast(pl.Utf8))
    )


def load_weekly_stats(season: str, demo: bool = False) -> pl.DataFrame:
    if demo:
        return pl.read_parquet(DEMO_DATA_DIR / "weekly_stats.parquet")
    df = nfl.load_player_stats(seasons=[int(season)])
    df = df.filter(pl.col("season_type") == "REG")
    return _fix_team_codes(df, "team", "opponent_team")


def load_snap_counts(season: str, demo: bool = False) -> pl.DataFrame:
    if demo:
        return pl.read_parquet(DEMO_DATA_DIR / "snap_counts.parquet")
    df = nfl.load_snap_counts(seasons=[int(season)])
    df = df.filter(pl.col("game_type") == "REG")
    return _fix_team_codes(df, "team", "opponent")


def load_schedules(season: str, demo: bool = False) -> pl.DataFrame:
    if demo:
        return pl.read_parquet(DEMO_DATA_DIR / "schedules.parquet")
    df = nfl.load_schedules(seasons=[int(season)])
    df = df.filter(pl.col("game_type") == "REG")
    return _fix_team_codes(df, "home_team", "away_team")


def is_bye_week(schedules: pl.DataFrame, team: str, week: int) -> bool:
    played = schedules.filter(
        (pl.col("week") == week) & ((pl.col("home_team") == team) | (pl.col("away_team") == team))
    )
    return played.height == 0


def opponent_this_week(schedules: pl.DataFrame, team: str, week: int) -> str | None:
    games = schedules.filter(
        (schedules["week"] == week)
        & ((schedules["home_team"] == team) | (schedules["away_team"] == team))
    )
    if games.height == 0:
        return None
    row = games.row(0, named=True)
    return row["away_team"] if row["home_team"] == team else row["home_team"]


def team_spread_and_total(
    schedules: pl.DataFrame, team: str, week: int
) -> tuple[float, float] | tuple[None, None]:
    """`team`'s real Vegas spread (positive = `team` favored, sign-flipped
    from the raw home-team-perspective `spread_line` when `team` is away)
    and the game's real total, for `week`. (None, None) if no scheduled game
    is found, or if the line hasn't been posted yet (nflverse leaves future
    weeks' lines null until closer to kickoff)."""
    games = schedules.filter(
        (pl.col("week") == week) & ((pl.col("home_team") == team) | (pl.col("away_team") == team))
    )
    if games.height == 0:
        return None, None
    row = games.row(0, named=True)
    spread_line = row["spread_line"]
    total_line = row["total_line"]
    if spread_line is None or total_line is None:
        return None, None
    team_spread = spread_line if row["home_team"] == team else -spread_line
    return team_spread, total_line


def load_expected_points(season: str, demo: bool = False) -> pl.DataFrame:
    """nflverse's own expected-fantasy-points model (actual vs. expected per
    player/week) -- the TD-rate/efficiency regression signal. No
    season_type/game_type column exists on this table (confirmed against
    the live nflreadpy payload); callers filter `week < current_week`
    themselves for no-leakage, same as every other per-week lookup here."""
    if demo:
        return pl.read_parquet(DEMO_DATA_DIR / "expected_points.parquet")
    return nfl.load_ff_opportunity(seasons=[int(season)])


def load_player_ages(demo: bool = False) -> pl.DataFrame:
    """sleeper_id -> age, position, from nflreadpy's player-id crosswalk.
    `age` is nflverse's own precomputed decimal age as of their data pull --
    used directly rather than re-derived from birthdate."""
    if demo:
        return pl.read_parquet(DEMO_DATA_DIR / "player_ages.parquet")
    ids = nfl.load_ff_playerids()
    return (
        ids.select(["sleeper_id", "age", "position"])
        .filter(pl.col("sleeper_id").is_not_null() & pl.col("age").is_not_null())
        .with_columns(pl.col("sleeper_id").cast(pl.Utf8))
    )


def expected_points_diff_ratio(
    expected_points: pl.DataFrame, gsis_id: str | None, before_week: int
) -> float | None:
    """Mean (actual - expected) / mean(expected) fantasy points over this
    player's games strictly before `before_week`. None if there's no prior
    data or expected points sum to 0 (can't compute a meaningful ratio)."""
    if gsis_id is None:
        return None
    rows = expected_points.filter(
        (pl.col("player_id") == gsis_id) & (pl.col("week") < before_week)
    )
    if rows.height == 0:
        return None
    actual_total = float(rows["total_fantasy_points"].sum())
    expected_total = float(rows["total_fantasy_points_exp"].sum())
    if expected_total == 0:
        return None
    return (actual_total - expected_total) / expected_total


def remaining_week_weights(
    schedules: pl.DataFrame,
    team: str,
    from_week: int,
    to_week: int,
    playoff_week_start: int,
    playoff_week_weight: float | None = None,
) -> list[float]:
    """One weight per week in [from_week, to_week]: 0.0 on team's bye,
    `playoff_week_weight` on a playoff week, else 1.0."""
    if playoff_week_weight is None:
        from core.waiver import PLAYOFF_WEEK_WEIGHT

        playoff_week_weight = PLAYOFF_WEEK_WEIGHT
    weights = []
    for week in range(from_week, to_week + 1):
        if is_bye_week(schedules, team, week):
            weights.append(0.0)
        elif week >= playoff_week_start:
            weights.append(playoff_week_weight)
        else:
            weights.append(1.0)
    return weights


def remaining_weeks_and_schedule_adjustments(
    schedules: pl.DataFrame,
    points_allowed: pl.DataFrame,
    team: str,
    position: str,
    weeks_played: int,
    from_week: int,
    to_week: int,
    before_week: int,
) -> tuple[list[int], float, float]:
    """The player's remaining week numbers in [from_week, to_week] with bye
    weeks excluded, plus the average core.projection.matchup_adjustment(...)
    and the average core.projection.game_script_adjustment(...) across
    those weeks' real scheduled opponents/Vegas lines. Every future week's
    opponent-defense quality is looked up using the SAME `before_week`
    (today's first-unplayed week) -- no future week can see data more
    recent than what's known today without leaking. A week with no posted
    Vegas line yet (nflverse leaves future lines null until closer to
    kickoff) contributes 0.0 to the game-script average, same "missing
    data -> no adjustment" convention used for missing matchup data."""
    from core.projection import game_script_adjustment, matchup_adjustment

    league_avg = league_avg_points_allowed_through_week(points_allowed, position, before_week)
    weeks: list[int] = []
    matchup_adjustments: list[float] = []
    game_script_adjustments: list[float] = []
    for week in range(from_week, to_week + 1):
        if is_bye_week(schedules, team, week):
            continue
        weeks.append(week)
        opponent = opponent_this_week(schedules, team, week)
        opp_allowed = (
            points_allowed_through_week(points_allowed, opponent, position, before_week)
            if opponent
            else None
        )
        if opp_allowed is None or league_avg is None:
            matchup_adjustments.append(0.0)
        else:
            matchup_adjustments.append(matchup_adjustment(opp_allowed, league_avg, weeks_played))

        team_spread, total_line = team_spread_and_total(schedules, team, week)
        if team_spread is None:
            game_script_adjustments.append(0.0)
        else:
            game_script_adjustments.append(game_script_adjustment(position, team_spread, total_line))
    avg_matchup_adjustment = mean(matchup_adjustments) if matchup_adjustments else 0.0
    avg_game_script_adjustment = mean(game_script_adjustments) if game_script_adjustments else 0.0
    return weeks, avg_matchup_adjustment, avg_game_script_adjustment


def weekly_fantasy_points(
    weekly_stats: pl.DataFrame, scoring_settings: dict[str, float]
) -> pl.DataFrame:
    """Adds a `fantasy_points` column computed from each row's raw stats
    under `scoring_settings` via core.scoring.score_stat_line (skill
    positions only -- see STAT_KEY_MAP)."""
    df = weekly_stats.filter(pl.col("position").is_in(SKILL_POSITIONS))
    df = df.with_columns(
        fum_lost=(
            pl.col("rushing_fumbles_lost").fill_null(0)
            + pl.col("receiving_fumbles_lost").fill_null(0)
            + pl.col("sack_fumbles_lost").fill_null(0)
        )
    )
    stat_cols = list(STAT_KEY_MAP) + ["fum_lost"]
    key_for = {**STAT_KEY_MAP, "fum_lost": "fum_lost"}

    points = [
        score_stat_line({key_for[c]: (row[c] or 0) for c in stat_cols}, scoring_settings)
        for row in df.select(stat_cols).iter_rows(named=True)
    ]
    return df.with_columns(pl.Series("fantasy_points", points))


def points_allowed_by_position(weekly_points: pl.DataFrame) -> pl.DataFrame:
    """Per (opponent_team, position, week): total fantasy points that
    opponent_team's defense allowed to that position."""
    return (
        weekly_points.group_by(["opponent_team", "position", "week"])
        .agg(pl.col("fantasy_points").sum().alias("points_allowed"))
        .sort(["position", "week", "opponent_team"])
    )


def points_allowed_through_week(
    points_allowed: pl.DataFrame, team: str, position: str, before_week: int
) -> float | None:
    """Average fantasy points `team`'s defense has allowed to `position` in
    weeks strictly before `before_week`. None if there's no prior data."""
    rows = points_allowed.filter(
        (pl.col("opponent_team") == team)
        & (pl.col("position") == position)
        & (pl.col("week") < before_week)
    )
    if rows.height == 0:
        return None
    return float(rows["points_allowed"].mean())


def league_avg_points_allowed_through_week(
    points_allowed: pl.DataFrame, position: str, before_week: int
) -> float | None:
    """League-wide average points allowed to `position` in weeks strictly
    before `before_week`. None if there's no prior data."""
    rows = points_allowed.filter((pl.col("position") == position) & (pl.col("week") < before_week))
    if rows.height == 0:
        return None
    return float(rows["points_allowed"].mean())


def opportunity_shares(
    weekly_stats: pl.DataFrame, snap_counts: pl.DataFrame, player_id_map: pl.DataFrame
) -> pl.DataFrame:
    """Per player/week: a position-appropriate opportunity share (WOPR --
    Weighted Opportunity Rating, 1.5*target_share + 0.7*air_yards_share,
    nflverse's own precomputed volume composite -- for WR/TE, carry share
    for RB, attempt share for QB) plus snap %, joined in via the
    sleeper_id/gsis_id/pfr_id crosswalk."""
    team_carries = weekly_stats.group_by(["team", "week"]).agg(
        pl.col("carries").sum().alias("team_carries")
    )
    team_attempts = weekly_stats.group_by(["team", "week"]).agg(
        pl.col("attempts").sum().alias("team_attempts")
    )

    df = weekly_stats.join(team_carries, on=["team", "week"], how="left")
    df = df.join(team_attempts, on=["team", "week"], how="left")
    df = df.with_columns(
        opportunity_share=pl.when(pl.col("position") == "RB")
        .then(pl.col("carries") / pl.col("team_carries"))
        .when(pl.col("position") == "QB")
        .then(pl.col("attempts") / pl.col("team_attempts"))
        .otherwise(pl.col("wopr"))
        .fill_null(0.0)
    )

    ids = player_id_map.select(["sleeper_id", "gsis_id", "pfr_id"])
    df = df.join(ids, left_on="player_id", right_on="gsis_id", how="left")

    snaps = snap_counts.select(["pfr_player_id", "week", "offense_pct"]).rename(
        {"pfr_player_id": "pfr_id", "offense_pct": "snap_pct"}
    )
    df = df.join(snaps, on=["pfr_id", "week"], how="left")
    df = df.with_columns(pl.col("snap_pct").fill_null(0.0))

    return df.select(
        [
            "sleeper_id",
            "player_id",
            "player_display_name",
            "position",
            "team",
            "week",
            "opportunity_share",
            "snap_pct",
        ]
    )


def player_weekly_points_and_shares(
    sleeper_id: str,
    weekly_points: pl.DataFrame,
    opportunity: pl.DataFrame,
    sleeper_to_gsis: dict[str, str | None],
    week: int,
) -> tuple[list[float], float, float]:
    """A player's (weekly_points list, recent_share, season_share) through
    weeks strictly before `week`. Shared by any caller that needs the same
    per-player feature extraction data/projections.py and data/waiver.py
    each already do inline."""
    gsis_id = sleeper_to_gsis.get(sleeper_id)
    prior_rows = weekly_points.filter(
        (weekly_points["player_id"] == gsis_id) & (weekly_points["week"] < week)
    ).sort("week")
    weekly_points_list = prior_rows["fantasy_points"].to_list()

    opp_rows = opportunity.filter(
        (opportunity["sleeper_id"] == sleeper_id) & (opportunity["week"] < week)
    ).sort("week")
    share_by_week = dict(zip(opp_rows["week"].to_list(), opp_rows["opportunity_share"].to_list()))
    prior_weeks = sorted(share_by_week)
    recent_weeks = prior_weeks[-3:]
    recent_share = mean(share_by_week[w] for w in recent_weeks) if recent_weeks else 0.0
    season_share = mean(share_by_week[w] for w in prior_weeks) if prior_weeks else 0.0

    return weekly_points_list, recent_share, season_share
