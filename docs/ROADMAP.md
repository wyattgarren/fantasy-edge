# Roadmap: fantasy-edge

A free fantasy football assistant for Sleeper leagues. You enter a Sleeper username, pick a league, and get start/sit calls, an optimized lineup, waiver targets, a matchup win probability, and trade checks.

**Ground rules**
- **No paid APIs.** Data comes from the public Sleeper API (no key) and nflverse stats via the `nflreadpy` package.
- **Numbers come from code, not from an AI.** Every projection and recommendation is computed by a transparent model you can test. An optional local LLM (Ollama) may only *explain* results that are already computed. It must never invent stats.
- **Verdict first, then depth.** Every recommendation leads with the call ("Start Puka over Waddle"), then the reasoning and the numbers behind it.
- **Works for any league.** The defaults match the owner's league (12-team, full PPR, QB/RB/RB/WR/WR/TE/FLEX/K/DEF), but scoring and roster slots are read from each league's settings.

**Stack:** Python 3.12, `httpx`, `pandas`, `nflreadpy`, Streamlit (UI, free hosting on Streamlit Community Cloud), SQLite/Parquet cache, `pytest`.

Implement **one phase at a time**. Each phase ends with the app running and tests passing.

---

## Phase 0: Project setup and Sleeper client

- Project layout: `app/` (Streamlit pages), `core/` (pure logic, no UI), `data/` (API clients and cache), `tests/`, `tests/fixtures/`.
- `data/sleeper.py` is a typed client for the read-only Sleeper API at `https://api.sleeper.app/v1`:
  - `get_user(username)` → `/user/{username}`
  - `get_leagues(user_id, season)` → `/user/{user_id}/leagues/nfl/{season}`
  - `get_league(league_id)`, `get_rosters(league_id)`, `get_league_users(league_id)`
  - `get_matchups(league_id, week)`, `get_transactions(league_id, week)`
  - `get_nfl_state()` → `/state/nfl` (current season and week)
  - `get_players()` → `/players/nfl`. This is a large file. **Cache it to disk and refresh at most once per day**, as Sleeper asks.
  - `get_trending(type="add"|"drop", lookback_hours=24, limit=25)`
- Wrap responses in Pydantic models: League, Roster, Matchup, Player, plus league `scoring_settings` and `roster_positions`.
- Add a simple response cache (SQLite or files with TTLs), a timeout, one retry, and clear errors (unknown username, private league, Sleeper unavailable).
- Keep well under Sleeper's rate limit (about 1000 calls/min). Batch work and lean on the cache.
- **Tests run offline.** Save real API responses once into `tests/fixtures/*.json` (a script `scripts/record_fixtures.py` does this). Tests mock `httpx` with those fixtures.
- Add README skeleton, `.gitignore` (cache dir, `.env`), and `requirements.txt`.

## Phase 1: Connect a league

- Streamlit home page: enter a Sleeper username, choose a season, pick a league from the dropdown, then pick your team. Save the choice in `st.session_state`, and support `?league=...&user=...` URL params so a link opens straight to a league.
- **My Team** page: roster grouped by position, current starters vs bench, injury status, bye weeks, and this week's opponent.
- **League** page: standings (W-L, points for/against), and each team's roster.
- `core/scoring.py` turns a raw stat line into fantasy points using the league's own `scoring_settings` (PPR, half PPR, bonuses, and so on).
- Tests: the scoring function matches Sleeper's posted weekly points for a few fixture players.

## Phase 2: Projection model and backtest

The heart of the app. Keep it simple, transparent, and measurable.

- `data/stats.py` loads weekly player stats, snap counts, and schedules from `nflreadpy`. Cache the results as Parquet.
- `core/projection.py` projects each player's fantasy points for a given week:
  - **Baseline:** a weighted average of recent fantasy points (for example, 50% last 3 weeks and 50% season-to-date), computed with league scoring.
  - **Opportunity adjustment:** trends in snap %, target share, carries, and red-zone touches. Opportunity predicts better than raw points.
  - **Matchup adjustment:** the opponent's fantasy points allowed to that position compared to the league average, shrunk toward average early in the season.
  - **Availability:** 0 on bye or when the player is Out/IR. Discount Questionable/Doubtful players by a configurable amount.
  - **Output:** `Projection { mean, floor (p20), ceiling (p80), std, components }`, where the spread comes from the player's week-to-week variance. Return `components` so the UI can show *why*.
- `core/backtest.py` replays past weeks using only data available before each week. It reports mean absolute error (MAE) by position and compares it against simple baselines (season average, last week). Results go in the README. This is the strongest resume piece in the project.
- Tests: no leakage of future data in the backtest, bye/injury handling, and known-input → known-output projection cases.

## Phase 3: Start/sit and lineup optimizer

- `core/lineup.py` builds the **optimal lineup** for the league's `roster_positions` (including FLEX/SUPER_FLEX eligibility). Fill the fixed slots by projection, then fill the flex slots from the remaining eligible players. Write a test that brute-forces small rosters to prove the result is optimal.
- **Risk mode:** a slider from *Safe* (rank by floor) to *Upside* (rank by ceiling). It's useful when you're a big underdog and need a boom week.
- **Start/Sit page:**
  - Verdict box: "Make these 2 changes: start X over Y (+3.4 pts)…"
  - Side-by-side compare of any two players, with mean, floor, ceiling, matchup, and opportunity trend.
  - Show each player's projection broken into its components (baseline, opportunity, matchup, availability), so every call is explainable.
- Tests: lineup slot eligibility, flex logic, and that bye/Out players never get started.

## Phase 4: Waiver wire

- Free agents = every active NFL player minus everyone on a roster in the league.
- Rank them with a **waiver score**: rest-of-season projection, opportunity trend (rising snap/target share), Sleeper trending adds, and **your team's need** (positional depth and upcoming byes).
- Suggest a **drop** for each add (your lowest rest-of-season value player at a position you're deep at).
- If the league uses FAAB (check `settings.waiver_type`), suggest a bid range as a % of remaining budget, based on the player's value and how many teams need that position.
- Page: verdict first ("Top add: X, drop Y, bid 8–12%"), then a sortable table of targets.

## Phase 5: Matchup simulator and trade analyzer

- `core/simulate.py` runs a **Monte Carlo** simulation of this week's matchup (for example 10,000 runs, drawing each starter's score from their projection distribution). It outputs win probability, the projected score range, and which of your players swing the result the most.
- `core/trade.py` takes players from both sides and compares rest-of-season value plus each team's **starting-lineup change** (does the trade improve your best lineup, not just your total?). Verdict: accept / decline / counter, with a short reason.
- Tests: the simulator's average matches the sum of the projections, the seed is fixed for repeatable tests, and the trade math is symmetric.

## Phase 6: Polish and portfolio

- **Optional AI explanations (free):** with `LLM_PROVIDER=ollama`, a local model turns the computed numbers into a short paragraph. Pass it only the computed figures and tell it not to add stats. Without Ollama, the app uses template sentences, and everything else still works.
- **Weekly report (optional):** a script (run by GitHub Actions on a schedule) posts Tuesday waiver targets and Thursday start/sit calls to a Discord webhook (free).
- **Demo mode:** a bundled sample league from the fixtures, so anyone can try the app without a Sleeper account.
- **Deploy** to Streamlit Community Cloud. Add the live link to the README and GitHub repo description.
- **README:** screenshots/GIF, an architecture diagram, how the projection model works, the **backtest results table**, and "what I'd improve next."
- **GitHub Actions** CI that runs `pytest` on every push.

## Notes and limits

- The Sleeper API is read-only, so the app suggests moves and you make them in the Sleeper app.
- Sleeper's projections endpoint isn't officially documented. Don't depend on it. If it's used at all, show it only as an optional comparison column.
- nflverse data usually updates within a day or so after games. Show a "data as of" timestamp on every page.
