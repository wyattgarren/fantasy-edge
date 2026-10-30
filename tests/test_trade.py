from core.trade import TradeSideResult, evaluate_side, evaluate_trade


def test_evaluate_side_known_values():
    roster_positions = ["RB", "RB", "WR"]
    current_positions = {"rb1": "RB", "rb2": "RB", "wr1": "WR", "wr2": "WR"}
    current_ros_values = {"rb1": 50.0, "rb2": 30.0, "wr1": 40.0, "wr2": 20.0}

    # before: RB=rb1(50)+rb2(30), WR=wr1(40) (best WR, wr2 benched) -> 120
    # give away rb2 (30), receive wr3 (45, WR)
    # after: RB=rb1(50)+empty(0), WR=wr3(45) (best WR now) -> 95
    result = evaluate_side(
        roster_positions,
        current_positions,
        current_ros_values,
        gives=["rb2"],
        receives=["wr3"],
        received_positions={"wr3": "WR"},
        received_ros_values={"wr3": 45.0},
    )

    assert result.lineup_value_before == 120.0
    assert result.lineup_value_after == 95.0
    assert result.lineup_value_change == -25.0
    assert result.value_change == 15.0  # gained 45, gave up 30


def test_value_change_is_symmetric_between_sides():
    # Side A gives p1 (value 50) for p2 (value 70); side B is the mirror.
    side_a = evaluate_side(
        roster_positions=["WR"],
        current_positions={"p1": "WR"},
        current_ros_values={"p1": 50.0},
        gives=["p1"],
        receives=["p2"],
        received_positions={"p2": "WR"},
        received_ros_values={"p2": 70.0},
    )
    side_b = evaluate_side(
        roster_positions=["WR"],
        current_positions={"p2": "WR"},
        current_ros_values={"p2": 70.0},
        gives=["p2"],
        receives=["p1"],
        received_positions={"p1": "WR"},
        received_ros_values={"p1": 50.0},
    )

    assert side_a.value_change == -side_b.value_change
    assert side_a.value_change == 20.0


def test_verdict_accept_when_lineup_improves():
    my_result = TradeSideResult(value_change=5.0, lineup_value_before=100.0, lineup_value_after=110.0, lineup_value_change=10.0)
    their_result = TradeSideResult(0.0, 0.0, 0.0, 0.0)

    evaluation = evaluate_trade(my_result, their_result)

    assert evaluation.verdict == "Accept"


def test_verdict_counter_when_value_up_but_lineup_down():
    my_result = TradeSideResult(value_change=10.0, lineup_value_before=100.0, lineup_value_after=95.0, lineup_value_change=-5.0)
    their_result = TradeSideResult(0.0, 0.0, 0.0, 0.0)

    evaluation = evaluate_trade(my_result, their_result)

    assert evaluation.verdict == "Counter"


def test_verdict_decline_when_lineup_and_value_both_down():
    my_result = TradeSideResult(value_change=-10.0, lineup_value_before=100.0, lineup_value_after=95.0, lineup_value_change=-5.0)
    their_result = TradeSideResult(0.0, 0.0, 0.0, 0.0)

    evaluation = evaluate_trade(my_result, their_result)

    assert evaluation.verdict == "Decline"


def test_verdict_counter_when_roughly_neutral():
    my_result = TradeSideResult(value_change=0.0, lineup_value_before=100.0, lineup_value_after=100.0, lineup_value_change=0.0)
    their_result = TradeSideResult(0.0, 0.0, 0.0, 0.0)

    evaluation = evaluate_trade(my_result, their_result)

    assert evaluation.verdict == "Counter"
