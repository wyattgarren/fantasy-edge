import itertools

from core.lineup import FLEX_ELIGIBLE, SUPER_FLEX_ELIGIBLE, optimal_lineup
from core.projection import Projection


def proj(mean: float, floor: float | None = None, ceiling: float | None = None) -> Projection:
    return Projection(
        mean=mean,
        floor=mean if floor is None else floor,
        ceiling=mean if ceiling is None else ceiling,
        std=0.0,
        components={},
    )


def eligible_for(slot: str, position: str) -> bool:
    if slot == "FLEX":
        return position in FLEX_ELIGIBLE
    if slot == "SUPER_FLEX":
        return position in SUPER_FLEX_ELIGIBLE
    return position == slot


def brute_force_max_value(
    starting_slots: list[str], player_positions: dict[str, str], values: dict[str, float]
) -> float:
    best = 0.0
    for combo in itertools.permutations(player_positions, len(starting_slots)):
        if all(eligible_for(slot, player_positions[pid]) for slot, pid in zip(starting_slots, combo)):
            best = max(best, sum(values[pid] for pid in combo))
    return best


def test_brute_force_optimality_simple_roster():
    roster_positions = ["QB", "RB", "RB", "FLEX", "BN"]
    player_positions = {
        "qb1": "QB",
        "rb1": "RB",
        "rb2": "RB",
        "rb3": "RB",
        "wr1": "WR",
        "wr2": "WR",
    }
    values = {"qb1": 20, "rb1": 15, "rb2": 12, "rb3": 10, "wr1": 11, "wr2": 8}
    projections = {pid: proj(v) for pid, v in values.items()}

    result = optimal_lineup(roster_positions, player_positions, projections, risk=0.5)

    starting_slots = [s for s in roster_positions if s != "BN"]
    expected_max = brute_force_max_value(starting_slots, player_positions, values)
    assert result.total_value == expected_max
    assert result.total_value == 58.0  # 20 + 15 + 12 + 11 (wr1 beats rb3 for FLEX)


def test_brute_force_optimality_with_super_flex():
    roster_positions = ["QB", "RB", "WR", "FLEX", "SUPER_FLEX", "BN"]
    player_positions = {
        "qb1": "QB",
        "qb2": "QB",
        "rb1": "RB",
        "rb2": "RB",
        "wr1": "WR",
        "wr2": "WR",
        "te1": "TE",
    }
    values = {"qb1": 25, "qb2": 18, "rb1": 16, "rb2": 9, "wr1": 14, "wr2": 7, "te1": 6}
    projections = {pid: proj(v) for pid, v in values.items()}

    result = optimal_lineup(roster_positions, player_positions, projections, risk=0.5)

    starting_slots = [s for s in roster_positions if s != "BN"]
    expected_max = brute_force_max_value(starting_slots, player_positions, values)
    assert result.total_value == expected_max


def test_flex_slot_prefers_higher_value_regardless_of_position():
    # 3rd RB outscores both WRs and must win FLEX over them
    roster_positions = ["RB", "RB", "FLEX"]
    player_positions = {"rb1": "RB", "rb2": "RB", "rb3": "RB", "wr1": "WR", "wr2": "WR"}
    values = {"rb1": 20, "rb2": 18, "rb3": 15, "wr1": 10, "wr2": 9}
    projections = {pid: proj(v) for pid, v in values.items()}

    result = optimal_lineup(roster_positions, player_positions, projections, risk=0.5)

    flex_assignment = next(a for a in result.assignments if a.slot == "FLEX")
    assert flex_assignment.player_id == "rb3"


def test_flex_filled_before_super_flex():
    # If SUPER_FLEX were filled first it could steal rb2 (the best SUPER_FLEX-
    # eligible leftover after the fixed RB slot), leaving FLEX with only a
    # worse WR -- filling FLEX first is required for the true optimum.
    roster_positions = ["RB", "FLEX", "SUPER_FLEX"]
    player_positions = {"rb1": "RB", "rb2": "RB", "wr1": "WR", "qb1": "QB"}
    values = {"rb1": 20, "rb2": 15, "wr1": 8, "qb1": 25}
    projections = {pid: proj(v) for pid, v in values.items()}

    result = optimal_lineup(roster_positions, player_positions, projections, risk=0.5)

    by_slot = {a.slot: a.player_id for a in result.assignments}
    assert by_slot["RB"] == "rb1"
    assert by_slot["FLEX"] == "rb2"  # best remaining RB/WR/TE
    assert by_slot["SUPER_FLEX"] == "qb1"  # best remaining QB/RB/WR/TE
    assert result.total_value == 20 + 15 + 25


def test_bye_or_out_player_never_preferred_over_available_alternative():
    roster_positions = ["WR"]
    player_positions = {"out_player": "WR", "healthy_player": "WR"}
    projections = {
        "out_player": proj(0.0),  # bye/Out: availability_multiplier zeroed this out
        "healthy_player": proj(9.0),
    }

    result = optimal_lineup(roster_positions, player_positions, projections, risk=0.5)

    assert result.assignments[0].player_id == "healthy_player"


def test_partial_roster_leaves_unfillable_slot_as_none():
    roster_positions = ["QB", "RB", "RB"]
    player_positions = {"qb1": "QB", "rb1": "RB"}
    projections = {"qb1": proj(20), "rb1": proj(15)}

    result = optimal_lineup(roster_positions, player_positions, projections, risk=0.5)

    player_ids = [a.player_id for a in result.assignments]
    assert player_ids.count(None) == 1  # only one RB total across two RB slots
    assert "qb1" in player_ids
    assert "rb1" in player_ids
    assert result.total_value == 35.0


def test_assignments_preserve_original_slot_order():
    # FLEX sits between the fixed slots here -- the output order must match
    # roster_positions exactly (including the repeated "RB") so callers can
    # zip it against Sleeper's roster.starters, which is in this same order.
    roster_positions = ["QB", "RB", "RB", "FLEX", "WR", "BN"]
    player_positions = {
        "qb1": "QB",
        "rb1": "RB",
        "rb2": "RB",
        "wr1": "WR",
        "wr2": "WR",
    }
    projections = {pid: proj(v) for pid, v in [("qb1", 20), ("rb1", 15), ("rb2", 12), ("wr1", 10), ("wr2", 8)]}

    result = optimal_lineup(roster_positions, player_positions, projections, risk=0.5)

    assert [a.slot for a in result.assignments] == ["QB", "RB", "RB", "FLEX", "WR"]
    assert [a.player_id for a in result.assignments] == ["qb1", "rb1", "rb2", "wr2", "wr1"]


def test_risk_slider_selects_floor_vs_ceiling():
    roster_positions = ["WR"]
    player_positions = {"safe": "WR", "boom_bust": "WR"}
    projections = {
        "safe": proj(mean=10, floor=9, ceiling=11),
        "boom_bust": proj(mean=10, floor=2, ceiling=18),
    }

    safe_result = optimal_lineup(roster_positions, player_positions, projections, risk=0.0)
    assert safe_result.assignments[0].player_id == "safe"  # 9 > 2

    upside_result = optimal_lineup(roster_positions, player_positions, projections, risk=1.0)
    assert upside_result.assignments[0].player_id == "boom_bust"  # 18 > 11
