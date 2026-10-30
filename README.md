# fantasy-edge

A free fantasy football assistant for Sleeper leagues. Enter a Sleeper
username, pick a league, and get start/sit calls, an optimized lineup,
waiver targets, a matchup win probability, and trade checks.

Every projection and recommendation is computed by transparent, testable
code — never invented by an AI. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for
the full project plan and ground rules.

## Stack

Python 3.12, `httpx`, `pandas`, `nflreadpy`, Streamlit, a file-based cache,
`pytest`.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Recording API fixtures

Tests run fully offline against saved fixtures. To (re-)record them from the
live Sleeper API:

```bash
python scripts/record_fixtures.py
```

## Running tests

```bash
pytest
```

## Running the app

```bash
streamlit run app/main.py
```

Enter a Sleeper username on the Home page to connect a league, then use the
My Team / League / Start/Sit pages. Start/Sit shows a live-projected optimal
lineup (with a Safe↔Upside risk slider), a verdict box of recommended swaps,
and a side-by-side player compare with full projection breakdowns. Works on
mobile browsers too (tested against an emulated iPhone viewport).

## Projection model backtest

`core/projection.py` projects each player's fantasy points from a recency-
weighted baseline, an opportunity-trend adjustment (snap %/target share/
carry share), and a matchup adjustment (opponent fantasy points allowed to
that position, shrunk toward league average early in the season).
`core/backtest.py` replays past weeks using only data available before each
week, and reports mean absolute error (MAE) by position against two naive
baselines. Reproduce with:

```bash
python scripts/run_backtest.py
```

Real results against the connected league's 2026 season, weeks 2-7 (84-312
data points per position; see `scripts/run_backtest.py` for methodology —
players need a full, gap-free game log through the last completed week to
be included):

| Position | Model MAE | Season-avg baseline MAE | Last-week baseline MAE |
|---|---|---|---|
| QB | 6.94 | 6.87 | 7.69 |
| RB | 6.18 | 5.75 | 6.83 |
| TE | 5.93 | 5.79 | 6.02 |
| WR | 5.23 | 4.73 | 5.73 |

The model clearly beats the naive "last week's score" baseline at every
position, but is slightly behind the "season average" baseline this early
in the season (only 1-6 prior weeks of data to compute opportunity trends
and matchup shrinkage from). **What I'd improve next:** revisit this once
more weeks of 2026 data accumulate — the opportunity/matchup adjustments
need a larger sample to add real signal rather than noise on top of the
baseline. Red-zone touches and K/DEF scoring are also out of scope for this
pass (see `data/stats.py`'s module docstring).

## Status

- [x] Phase 0: Project setup and Sleeper client
- [x] Phase 1: Connect a league
- [x] Phase 2: Projection model and backtest
- [x] Phase 3: Start/sit and lineup optimizer
- [ ] Phase 4: Waiver wire
- [ ] Phase 5: Matchup simulator and trade analyzer
- [ ] Phase 6: Polish and portfolio
