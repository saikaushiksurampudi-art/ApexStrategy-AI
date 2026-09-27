"""Analytics correctness, checked against a hand-verifiable fixture dataset."""

from __future__ import annotations

from app.services import analytics


def test_resolve_driver_by_ref_code_and_surname(db_session):
    for identifier in ("apex", "APX", "Apex", "Ada Apex"):
        driver = analytics.resolve_driver(db_session, identifier)
        assert driver is not None, identifier
        assert driver.ref == "apex"


def test_resolve_driver_unknown_returns_none(db_session):
    assert analytics.resolve_driver(db_session, "nobody-at-all") is None


def test_driver_summary_counts(db_session):
    driver = analytics.resolve_driver(db_session, "apex")
    summary = analytics.driver_summary(db_session, driver)

    # Apex: 6 races, wins in 2023R1, 2024R1, 2025R1, 2025R2 -> 4 wins,
    # plus a P2 in 2023R2 (5 podiums) and one retirement in 2024R2.
    assert summary.races == 6
    assert summary.wins == 4
    assert summary.podiums == 5
    assert summary.dnfs == 1
    assert summary.total_points == 118.0
    assert summary.best_finish == 1
    assert round(summary.dnf_rate, 4) == round(1 / 6, 4)


def test_driver_summary_scoped_to_season(db_session):
    driver = analytics.resolve_driver(db_session, "apex")
    summary = analytics.driver_summary(db_session, driver, seasons=[2025])
    assert summary.races == 2
    assert summary.wins == 2
    assert summary.total_points == 50.0


def test_driver_summary_scoped_to_circuit(db_session):
    driver = analytics.resolve_driver(db_session, "apex")
    circuit = analytics.resolve_circuit(db_session, "alpha")
    summary = analytics.driver_summary(db_session, driver, circuit_id=circuit.id)
    # Alpha hosts round 1 of each season: three wins for Apex.
    assert summary.races == 3
    assert summary.wins == 3


def test_head_to_head_excludes_races_where_one_driver_retired(db_session):
    """A retirement must not count as a 'loss' in the head-to-head tally."""
    apex = analytics.resolve_driver(db_session, "apex")
    bolt = analytics.resolve_driver(db_session, "bolt")
    comparison = analytics.head_to_head(db_session, apex, bolt)

    assert comparison["shared_races"] == 6
    # Apex retired in 2024 R2, so only 5 races have both classified.
    assert comparison["race_head_to_head"]["counted"] == 5
    assert comparison["race_head_to_head"]["a"] == 4   # 2023R1, 2024R1, 2025R1, 2025R2
    assert comparison["race_head_to_head"]["b"] == 1   # 2023R2
    # Qualifying always has both, so all six count.
    assert comparison["qualifying_head_to_head"]["counted"] == 6


def test_head_to_head_timeline_is_chronological(db_session):
    apex = analytics.resolve_driver(db_session, "apex")
    cruz = analytics.resolve_driver(db_session, "cruz")
    timeline = analytics.head_to_head(db_session, apex, cruz)["timeline"]
    keys = [(row["season"], row["round"]) for row in timeline]
    assert keys == sorted(keys)


def test_circuit_history_grid_buckets(db_session):
    circuit = analytics.resolve_circuit(db_session, "alpha")
    history = analytics.circuit_history(db_session, circuit)

    assert history["races_counted"] == 3
    assert history["seasons_covered"] == [2023, 2024, 2025]

    # Pole-sitter won all three races at Alpha.
    assert history["pole_to_win_rate"]["poles_counted"] == 3
    assert history["pole_to_win_rate"]["win_rate"] == 1.0

    buckets = {row["bucket"]: row for row in history["grid_analysis"]}
    assert buckets["P1 (pole)"]["starts"] == 3
    assert buckets["P1 (pole)"]["podium_rate"] == 1.0


def test_circuit_pit_strategy_distribution(db_session):
    """Alpha was seeded with two stops per driver, Beta with one."""
    alpha = analytics.resolve_circuit(db_session, "alpha")
    beta = analytics.resolve_circuit(db_session, "beta")

    alpha_strategy = analytics.circuit_pit_strategy(db_session, alpha)
    assert alpha_strategy["avg_stops"] == 2.0
    assert alpha_strategy["stop_distribution"][0]["stops"] == 2

    beta_strategy = analytics.circuit_pit_strategy(db_session, beta)
    assert beta_strategy["avg_stops"] == 1.0


def test_qualifying_trend_computes_gap_to_pole(db_session):
    driver = analytics.resolve_driver(db_session, "bolt")
    trend = analytics.driver_qualifying_trend(db_session, driver)
    assert len(trend) == 6
    for row in trend:
        assert row["gap_to_pole_s"] is not None
        assert row["gap_to_pole_s"] >= 0  # nobody is faster than pole


def test_recent_form_is_strictly_backward_looking(db_session):
    """Form for a race must never include that race's own result."""
    from app.models import Race

    driver = analytics.resolve_driver(db_session, "apex")
    first_race = db_session.query(Race).filter_by(season=2023, round=1).one()
    form = analytics.driver_recent_form(db_session, driver.id, first_race)
    # Nothing precedes the very first race in the dataset.
    assert form["races_counted"] == 0

    later = db_session.query(Race).filter_by(season=2025, round=2).one()
    form = analytics.driver_recent_form(db_session, driver.id, later)
    assert form["races_counted"] == 5


def test_constructor_summary_reliability(db_session):
    constructor = analytics.resolve_constructor(db_session, "steady")
    summary = analytics.constructor_summary(db_session, constructor)
    # Steady GP: 12 entries, two retirements (cruz 2023R2, dash 2024R1).
    assert summary["race_entries"] == 12
    assert summary["dnfs"] == 2
    assert round(summary["reliability_rate"], 4) == round(10 / 12, 4)


def test_season_standings(db_session):
    standings = analytics.season_standings(db_session, 2025)
    assert standings["season"] == 2025
    assert standings["through_round"] == 2
    assert standings["drivers"][0]["name"] == "Ada Apex"
    assert standings["constructors"][0]["name"] == "Swift Racing"


def test_search_finds_entities(db_session):
    results = analytics.search_entities(db_session, "ap")
    assert any(d["ref"] == "apex" for d in results["drivers"])
    results = analytics.search_entities(db_session, "alpha")
    assert any(c["ref"] == "alpha" for c in results["circuits"])
