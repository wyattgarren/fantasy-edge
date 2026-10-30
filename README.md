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

Not yet available — the Streamlit UI lands in Phase 1.

## Status

- [x] Phase 0: Project setup and Sleeper client
- [ ] Phase 1: Connect a league
- [ ] Phase 2: Projection model and backtest
- [ ] Phase 3: Start/sit and lineup optimizer
- [ ] Phase 4: Waiver wire
- [ ] Phase 5: Matchup simulator and trade analyzer
- [ ] Phase 6: Polish and portfolio
