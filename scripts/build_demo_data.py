"""Builds the bundled demo-mode snapshot under data/demo_data/, from a real,
already-scored week of the owner's real league, so a visitor with no
Sleeper account can try every page with realistic numbers and zero network
calls (see data/demo.py and data/stats.py's `demo=` kwarg).

Run manually (requires network access):

    python scripts/build_demo_data.py

Re-run occasionally to refresh the snapshot against a newer completed week.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import data.stats as stats  # noqa: E402
from data.cache import FileCache  # noqa: E402
from data.demo import DEMO_LEAGUE_ID, DEMO_USER_ID, DEMO_USERNAME  # noqa: E402
from data.sleeper import SleeperClient  # noqa: E402

USERNAME = "thesplurggler"
LEAGUE_ID = "1391465605172834304"
SEASON = "2026"
# A week that's fully scored (every roster has real, non-zero points) --
# NOT necessarily the current week, which may still be in progress.
WEEK = 7

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}

SLEEPER_DIR = REPO_ROOT / "data" / "demo_data" / "sleeper"
STATS_DIR = REPO_ROOT / "data" / "demo_data" / "stats"


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2))
    print(f"wrote {path.relative_to(REPO_ROOT)}")


def main() -> None:
    SLEEPER_DIR.mkdir(parents=True, exist_ok=True)
    STATS_DIR.mkdir(parents=True, exist_ok=True)

    client = SleeperClient(cache=FileCache(".cache"))

    user = client.get_user(USERNAME)
    league = client.get_league(LEAGUE_ID)
    rosters = client.get_rosters(LEAGUE_ID)
    league_users = client.get_league_users(LEAGUE_ID)
    matchups = client.get_matchups(LEAGUE_ID, WEEK)
    transactions = client.get_transactions(LEAGUE_ID, WEEK)
    trending = client.get_trending(type="add", lookback_hours=24, limit=100)
    nfl_state = client.get_nfl_state()
    all_players = client.get_players()

    # Real, non-demo stats pull -- used both to pick which players belong in
    # the trimmed demo player pool, and to build the trimmed parquet
    # snapshot itself.
    weekly_stats = stats.load_weekly_stats(SEASON)
    id_map = stats.load_player_id_map()
    snap_counts = stats.load_snap_counts(SEASON)
    schedules = stats.load_schedules(SEASON)
    expected_points = stats.load_expected_points(SEASON)
    player_ages = stats.load_player_ages()

    sleeper_to_gsis = dict(zip(id_map["sleeper_id"].to_list(), id_map["gsis_id"].to_list()))
    played_gsis_ids = set(weekly_stats["player_id"].unique().to_list())

    rostered_ids = {pid for roster in rosters for pid in roster.players}
    free_agent_ids = {
        pid
        for pid, player in all_players.items()
        if pid not in rostered_ids
        and player.status == "Active"
        and player.position in SKILL_POSITIONS
        and sleeper_to_gsis.get(pid) in played_gsis_ids
    }
    demo_player_ids = rostered_ids | free_agent_ids
    print(f"demo player pool: {len(demo_player_ids)} ({len(rostered_ids)} rostered + "
          f"{len(free_agent_ids)} free agents)")

    # -- Rewrite IDs so demo data can never collide with a real league/user --
    league_json = league.model_dump()
    league_json["league_id"] = DEMO_LEAGUE_ID

    user_json = user.model_dump()
    user_json["user_id"] = DEMO_USER_ID
    user_json["username"] = DEMO_USERNAME

    rosters_json = []
    for roster in rosters:
        roster_json = roster.model_dump()
        roster_json["league_id"] = DEMO_LEAGUE_ID
        if roster.owner_id == user.user_id:
            roster_json["owner_id"] = DEMO_USER_ID
        rosters_json.append(roster_json)

    nfl_state_json = nfl_state.model_dump()
    nfl_state_json["week"] = WEEK
    nfl_state_json["display_week"] = WEEK

    players_json = {
        pid: all_players[pid].model_dump() for pid in demo_player_ids if pid in all_players
    }

    write_json(SLEEPER_DIR / "league.json", league_json)
    write_json(SLEEPER_DIR / "user.json", user_json)
    write_json(SLEEPER_DIR / "rosters.json", rosters_json)
    write_json(SLEEPER_DIR / "league_users.json", [u.model_dump() for u in league_users])
    write_json(SLEEPER_DIR / "matchups.json", [m.model_dump() for m in matchups])
    write_json(SLEEPER_DIR / "transactions.json", [t.model_dump() for t in transactions])
    write_json(SLEEPER_DIR / "trending_add.json", [t.model_dump() for t in trending])
    write_json(SLEEPER_DIR / "nfl_state.json", nfl_state_json)
    write_json(SLEEPER_DIR / "players.json", players_json)

    demo_gsis_ids = {sleeper_to_gsis.get(pid) for pid in demo_player_ids} - {None}
    weekly_stats.filter(weekly_stats["player_id"].is_in(list(demo_gsis_ids))).write_parquet(
        STATS_DIR / "weekly_stats.parquet"
    )
    id_map.filter(id_map["sleeper_id"].is_in(list(demo_player_ids))).write_parquet(
        STATS_DIR / "player_ids.parquet"
    )
    demo_pfr_ids = set(
        id_map.filter(id_map["sleeper_id"].is_in(list(demo_player_ids)))["pfr_id"].to_list()
    ) - {None}
    snap_counts.filter(snap_counts["pfr_player_id"].is_in(list(demo_pfr_ids))).write_parquet(
        STATS_DIR / "snap_counts.parquet"
    )
    # Schedules are league/team-wide, not per-player -- keep the full season.
    schedules.write_parquet(STATS_DIR / "schedules.parquet")
    expected_points.filter(expected_points["player_id"].is_in(list(demo_gsis_ids))).write_parquet(
        STATS_DIR / "expected_points.parquet"
    )
    player_ages.filter(player_ages["sleeper_id"].is_in(list(demo_player_ids))).write_parquet(
        STATS_DIR / "player_ages.parquet"
    )
    print(f"wrote {STATS_DIR.relative_to(REPO_ROOT)}/*.parquet")


if __name__ == "__main__":
    main()
