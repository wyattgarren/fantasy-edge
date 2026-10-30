"""Builds the optimal starting lineup for a league's roster_positions.

Fixed slots (QB/RB/WR/TE/K/DEF/...) can only be filled by their own
position, so each one independently grabs its own best remaining
same-position player -- that's always optimal, since there's no
cross-position contention for those slots. FLEX and SUPER_FLEX are then
filled most-restrictive-first (FLEX before SUPER_FLEX, since SUPER_FLEX's
eligible set is a superset of FLEX's): filling SUPER_FLEX first could hand
it a RB/WR/TE that FLEX needed instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.projection import Projection

FLEX_ELIGIBLE = {"RB", "WR", "TE"}
SUPER_FLEX_ELIGIBLE = {"QB", "RB", "WR", "TE"}
FLEX_SLOTS_IN_FILL_ORDER = ["FLEX", "SUPER_FLEX"]
NON_STARTING_SLOTS = {"BN"}


@dataclass
class SlotAssignment:
    slot: str
    player_id: str | None


@dataclass
class OptimalLineup:
    assignments: list[SlotAssignment]
    bench: list[str]
    total_value: float


def lineup_value(projection: Projection, risk: float) -> float:
    """risk=0.0 -> floor (Safe), 1.0 -> ceiling (Upside), 0.5 -> mean."""
    return projection.floor + risk * (projection.ceiling - projection.floor)


def optimal_lineup(
    roster_positions: list[str],
    player_positions: dict[str, str],
    projections: dict[str, Projection],
    risk: float = 0.5,
) -> OptimalLineup:
    values = {
        pid: lineup_value(proj, risk) for pid, proj in projections.items() if pid in player_positions
    }
    remaining = {pid for pid in player_positions if pid in values}

    def best_remaining(eligible_positions: set[str]) -> str | None:
        candidates = [pid for pid in remaining if player_positions[pid] in eligible_positions]
        if not candidates:
            return None
        return max(candidates, key=lambda pid: values[pid])

    # Indices (not slot names) are the source of truth for output order --
    # roster_positions can repeat a slot name ("RB","RB") or interleave FLEX
    # between fixed slots, so processing must be priority-ordered (fixed,
    # then FLEX, then SUPER_FLEX, for optimality) while the *output* must
    # still land back in the caller's original slot order (e.g. to zip
    # against Sleeper's roster.starters).
    indexed_slots = [
        (i, slot) for i, slot in enumerate(roster_positions) if slot not in NON_STARTING_SLOTS
    ]
    fixed = [(i, s) for i, s in indexed_slots if s not in FLEX_SLOTS_IN_FILL_ORDER]
    flex = [(i, s) for i, s in indexed_slots if s == "FLEX"]
    super_flex = [(i, s) for i, s in indexed_slots if s == "SUPER_FLEX"]

    results: dict[int, SlotAssignment] = {}
    for i, slot in fixed:
        pid = best_remaining({slot})
        results[i] = SlotAssignment(slot=slot, player_id=pid)
        if pid is not None:
            remaining.discard(pid)
    for i, slot in flex:
        pid = best_remaining(FLEX_ELIGIBLE)
        results[i] = SlotAssignment(slot=slot, player_id=pid)
        if pid is not None:
            remaining.discard(pid)
    for i, slot in super_flex:
        pid = best_remaining(SUPER_FLEX_ELIGIBLE)
        results[i] = SlotAssignment(slot=slot, player_id=pid)
        if pid is not None:
            remaining.discard(pid)

    assignments = [results[i] for i, _ in indexed_slots]

    total_value = sum(
        values[a.player_id] for a in assignments if a.player_id is not None
    )
    assigned_pids = {a.player_id for a in assignments}
    bench = sorted(pid for pid in player_positions if pid not in assigned_pids)

    return OptimalLineup(assignments=assignments, bench=bench, total_value=total_value)
