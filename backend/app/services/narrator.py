"""Deterministic, template-based answer writer.

This is the fallback when Amazon Bedrock is disabled or unreachable, and it is
the reason the product works on a laptop with no AWS account. It reads exactly
the same context pack the LLM would receive and renders it as prose.

It is less fluent than a language model. It is also incapable of inventing a
statistic, which makes it a useful reference point: if the Bedrock answer says
something the narrator cannot, that claim deserves scrutiny.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

PERCENT = "{:.0%}"


def _pct(value: Optional[float]) -> str:
    return PERCENT.format(value) if isinstance(value, (int, float)) else "n/a"


def _num(value: Optional[float], places: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{places}f}".rstrip("0").rstrip(".") if places else str(value)


def _season_range(seasons: List[int]) -> str:
    if not seasons:
        return "the available seasons"
    if len(seasons) == 1:
        return str(seasons[0])
    return f"{min(seasons)}-{max(seasons)}"


def generate(question: str, context: Dict[str, Any]) -> str:
    """Render a context pack as a readable answer."""
    facts = context.get("facts", {})
    notes = context.get("notes", [])
    intent = context.get("intent", "general")

    if not facts:
        lines = ["I don't have data in the database to answer that."]
        lines.extend(notes)
        lines.append(
            "Try naming a driver, team or circuit -- for example "
            '"Compare Verstappen and Norris at Monza".'
        )
        return "\n\n".join(lines)

    sections: List[str] = []
    renderers = {
        "head_to_head": _render_head_to_head,
        "prediction": _render_prediction,
        "pit_strategy": _render_tyre_strategy,
        "circuit_history": _render_circuit,
        "qualifying_trends": _render_qualifying,
        "standings": _render_standings,
        "drivers": _render_drivers,
        "race": _render_race,
    }
    # Lead with the block that matches the intent, then add supporting ones.
    priority = {
        "comparison": ["head_to_head", "drivers"],
        "prediction": ["prediction", "circuit_history"],
        "tyre_strategy": ["pit_strategy", "circuit_history"],
        "circuit": ["circuit_history", "drivers"],
        "qualifying": ["qualifying_trends", "drivers"],
        "standings": ["standings"],
        "driver_profile": ["drivers"],
        "general": ["standings", "race"],
    }.get(intent, [])

    ordered = [key for key in priority if key in facts]
    ordered += [key for key in facts if key not in ordered and key in renderers]

    for key in ordered[:3]:
        rendered = renderers[key](facts[key])
        if rendered:
            sections.append(rendered)

    if notes:
        sections.append("\n".join(f"_{note}_" for note in notes))

    return "\n\n".join(section for section in sections if section)


# ---------------------------------------------------------------------------
# Block renderers
# ---------------------------------------------------------------------------
def _render_head_to_head(block: Dict[str, Any]) -> str:
    a, b = block["driver_a"], block["driver_b"]
    race_h2h = block["race_head_to_head"]
    quali_h2h = block["qualifying_head_to_head"]

    lines = [
        f"**{a['name']} vs {b['name']}** across {block['shared_races']} shared races."
    ]
    if race_h2h["counted"]:
        leader = a["name"] if race_h2h["a"] > race_h2h["b"] else b["name"]
        lines.append(
            f"- Race finishes (both classified, {race_h2h['counted']} races): "
            f"**{race_h2h['a']}-{race_h2h['b']}** to {leader}."
        )
    if quali_h2h["counted"]:
        leader = a["name"] if quali_h2h["a"] > quali_h2h["b"] else b["name"]
        lines.append(
            f"- Qualifying ({quali_h2h['counted']} sessions): "
            f"**{quali_h2h['a']}-{quali_h2h['b']}** to {leader}."
        )

    for driver in (a, b):
        lines.append(
            f"- {driver['name']}: {driver['wins']} wins, {driver['podiums']} podiums, "
            f"{_num(driver['total_points'], 1)} points from {driver['races']} races "
            f"(avg finish {_num(driver['avg_finish'])}, avg grid "
            f"{_num(driver['avg_grid'])}, DNF rate {_pct(driver['dnf_rate'])})."
        )

    lines.append(
        f"Scope: {_season_range(a.get('seasons') or [])}. Head-to-head counts only "
        "races where both drivers were classified, so retirements are excluded "
        "from the tally but still visible in the DNF rates."
    )
    return "\n".join(lines)


def _render_prediction(block: Dict[str, Any]) -> str:
    lines = [
        f"**Model estimates for the {block['race']} "
        f"({block['season']}, round {block['round']}) at {block['circuit']}.**"
    ]
    if block.get("grid_source") == "projected":
        lines.append(
            "_Qualifying has not run, so the starting grid is projected from "
            "recent qualifying form._"
        )

    focus = block.get("focus_drivers") or []
    shown = focus or block.get("top_contenders", [])[:5]
    for item in shown:
        lines.append(
            f"- **{item['driver']}** ({item['constructor']}, P{item['grid']} on the "
            f"grid): podium {_pct(item['podium_probability'])}, points "
            f"{_pct(item['points_probability'])}."
        )
        for factor in (item.get("top_factors") or [])[:2]:
            lines.append(
                f"    - {factor['direction'].capitalize()} the podium estimate by "
                f"{abs(factor['impact']):.1%}: {factor['label']} "
                f"({_num(factor['value'])} vs a typical {_num(factor['baseline'])})."
            )

    evaluation = block.get("model_evaluation")
    if isinstance(evaluation, dict) and evaluation.get("podium"):
        podium_eval = evaluation["podium"]
        verdict = "better than" if podium_eval.get("beats_baseline") else "no better than"
        lines.append(
            f"Model {block['model_version']} scored a log loss of "
            f"{podium_eval['model']['log_loss']} on held-out seasons, which is "
            f"{verdict} the {podium_eval['best_baseline']} baseline "
            f"({podium_eval['baseline_scores']['log_loss']})."
        )

    lines.append(f"_{block['disclaimer']}_")
    return "\n".join(lines)


def _render_tyre_strategy(block: Dict[str, Any]) -> str:
    if not block.get("sample_size"):
        return (
            "No pit-stop records are held for this circuit, so I can't describe "
            "its stop patterns."
        )

    distribution = block["stop_distribution"]
    lines = ["**Observed pit-stop patterns at this circuit.**"]
    for entry in distribution:
        label = "stop" if entry["stops"] == 1 else "stops"
        lines.append(
            f"- {entry['stops']} {label}: {_pct(entry['share'])} of "
            f"{block['sample_size']} driver-races ({entry['driver_races']})."
        )
    lines.append(
        f"Average stops per driver: {_num(block['avg_stops'])}. "
        f"Median stationary time: {_num(block['median_stop_duration_s'])}s"
        + (
            f", against an estimated total pit-lane loss of "
            f"{_num(block['pit_loss_seconds'])}s."
            if block.get("pit_loss_seconds")
            else "."
        )
    )

    # Read the risk straight off the observed distribution rather than
    # asserting a generic rule.
    one_stop = next((e for e in distribution if e["stops"] == 1), None)
    one_stop_share = one_stop["share"] if one_stop else 0.0
    dominant = max(distribution, key=lambda e: e["driver_races"]) if distribution else None

    if one_stop_share >= 0.6:
        lines.append(
            f"A one-stop is the established pattern here: {_pct(one_stop_share)} of "
            "the sample did exactly that, so committing to it follows the field "
            "rather than gambling against it."
        )
    elif dominant is not None:
        dominant_label = "stop" if dominant["stops"] == 1 else "stops"
        lines.append(
            f"A one-stop looks risky here. Only {_pct(one_stop_share)} of the "
            f"{block['sample_size']} driver-races in the sample used one, while the "
            f"most common choice was {dominant['stops']} {dominant_label} "
            f"({_pct(dominant['share'])}). Going long enough to stop once means "
            "asking the tyre to survive a stint the field has rarely attempted at "
            "this circuit, and losing that gamble usually costs more than the "
            f"~{_num(block.get('pit_loss_seconds') or block.get('median_stop_duration_s'))}s "
            "an extra stop would have cost."
        )
    return "\n".join(lines)


def _render_circuit(block: Dict[str, Any]) -> str:
    circuit = block["circuit"]
    lines = [
        f"**{circuit['name']}** ({circuit.get('locality')}, {circuit.get('country')}) "
        f"-- {block['races_counted']} races in the database "
        f"({_season_range(block['seasons_covered'])})."
    ]
    if circuit.get("tyre_degradation") or circuit.get("overtaking_difficulty"):
        lines.append(
            f"- Track character: {circuit.get('circuit_type') or 'unclassified'} "
            f"circuit, {circuit.get('tyre_degradation') or 'unknown'} tyre "
            f"degradation, {circuit.get('overtaking_difficulty') or 'unknown'} "
            "overtaking difficulty."
        )
    if circuit.get("notes"):
        lines.append(f"- {circuit['notes']}")

    top = block.get("top_drivers", [])[:5]
    if top:
        lines.append("Strongest records here:")
        for driver in top:
            lines.append(
                f"- {driver['name']} ({driver['constructor']}): {driver['wins']} wins, "
                f"{driver['podiums']} podiums from {driver['starts']} starts, "
                f"average finish {_num(driver['avg_finish'])}."
            )

    pole = block.get("pole_to_win_rate") or {}
    if pole.get("poles_counted"):
        lines.append(
            f"Pole position has converted to a win {_pct(pole['win_rate'])} of the "
            f"time here ({pole['poles_counted']} races) and to a podium "
            f"{_pct(pole['podium_rate'])} of the time."
        )
    return "\n".join(lines)


def _render_qualifying(block: Dict[str, Any]) -> str:
    lines = ["**Qualifying record.**"]
    for name, sessions in block.items():
        if not sessions:
            continue
        positions = [s["position"] for s in sessions if s.get("position")]
        gaps = [s["gap_to_pole_s"] for s in sessions if s.get("gap_to_pole_s") is not None]
        q3 = sum(1 for s in sessions if s.get("reached_q3"))
        lines.append(
            f"- {name}: average grid slot {_num(sum(positions) / len(positions))} "
            f"over the last {len(sessions)} sessions, reaching Q3 {q3} times"
            + (
                f", averaging {_num(sum(gaps) / len(gaps), 3)}s off pole."
                if gaps
                else "."
            )
        )
    return "\n".join(lines)


def _render_standings(block: Dict[str, Any]) -> str:
    lines = [
        f"**{block['season']} championship standings** "
        f"(through round {block.get('through_round')})."
    ]
    for entry in block.get("drivers", [])[:5]:
        lines.append(
            f"- P{entry['position']} {entry['name']} ({entry['constructor']}): "
            f"{_num(entry['points'], 1)} points, {entry['wins']} wins."
        )
    for entry in block.get("constructors", [])[:3]:
        lines.append(
            f"- Constructors P{entry['position']} {entry['name']}: "
            f"{_num(entry['points'], 1)} points."
        )
    return "\n".join(lines)


def _render_drivers(block: List[Dict[str, Any]]) -> str:
    lines = []
    for driver in block:
        lines.append(
            f"**{driver['name']}** ({driver.get('constructor') or 'unknown team'}) "
            f"-- {driver['races']} races in {_season_range(driver.get('seasons') or [])}: "
            f"{driver['wins']} wins, {driver['podiums']} podiums, "
            f"{driver['points_finishes']} points finishes, "
            f"{_num(driver['total_points'], 1)} points. "
            f"Average finish {_num(driver['avg_finish'])} from an average grid slot "
            f"of {_num(driver['avg_grid'])}; DNF rate {_pct(driver['dnf_rate'])}."
        )
    return "\n\n".join(lines)


def _render_race(block: Dict[str, Any]) -> str:
    lines = [
        f"**{block['name']}** ({block['season']}, round {block['round']}) at "
        f"{block['circuit']['name']}"
        + (f", {block['date']}." if block.get("date") else ".")
    ]
    for entry in block.get("podium", []):
        lines.append(
            f"- P{entry['position']} {entry['driver']} ({entry['constructor']}), "
            f"from P{entry['grid']} on the grid."
        )
    return "\n".join(lines)
