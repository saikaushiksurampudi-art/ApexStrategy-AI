"""Curated, editorial circuit metadata.

The Ergast/Jolpica dataset carries no track-character information, but tyre and
strategy explanations need it. These values are hand-maintained editorial
judgements (not measurements) and are surfaced to users as such.

``pit_loss_seconds`` is the approximate total time lost driving through the pit
lane relative to staying on track, as commonly quoted by broadcasters.
"""

from __future__ import annotations

from typing import Dict, TypedDict


class CircuitMeta(TypedDict, total=False):
    circuit_type: str
    overtaking_difficulty: str
    tyre_degradation: str
    pit_loss_seconds: float
    drs_zones: int
    notes: str


CIRCUIT_META: Dict[str, CircuitMeta] = {
    "bahrain": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "low",
        "tyre_degradation": "high",
        "pit_loss_seconds": 23.0,
        "drs_zones": 3,
        "notes": "Abrasive surface and high rear-tyre loading; traditionally a two- or three-stop race.",
    },
    "jeddah": {
        "circuit_type": "street",
        "overtaking_difficulty": "medium",
        "tyre_degradation": "low",
        "pit_loss_seconds": 19.5,
        "drs_zones": 3,
        "notes": "Very high average speed; low degradation makes a one-stop the default, but safety-car risk is high.",
    },
    "albert_park": {
        "circuit_type": "hybrid",
        "overtaking_difficulty": "medium",
        "tyre_degradation": "low",
        "pit_loss_seconds": 19.0,
        "drs_zones": 4,
        "notes": "Resurfaced and fast; low degradation rewards track position over strategy.",
    },
    "suzuka": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "high",
        "tyre_degradation": "high",
        "pit_loss_seconds": 22.0,
        "drs_zones": 2,
        "notes": "Sustained high-energy corners punish front-left tyres; two-stop is often optimal.",
    },
    "shanghai": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "low",
        "tyre_degradation": "high",
        "pit_loss_seconds": 22.0,
        "drs_zones": 2,
        "notes": "Long turn 1-2-3 complex and a long back straight; front-left limited.",
    },
    "miami": {
        "circuit_type": "street",
        "overtaking_difficulty": "medium",
        "tyre_degradation": "medium",
        "pit_loss_seconds": 19.0,
        "drs_zones": 3,
        "notes": "High ambient temperatures drive overheating rather than wear.",
    },
    "imola": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "high",
        "tyre_degradation": "low",
        "pit_loss_seconds": 26.0,
        "drs_zones": 2,
        "notes": "Narrow and hard to pass; a long pit lane makes undercutting expensive.",
    },
    "monaco": {
        "circuit_type": "street",
        "overtaking_difficulty": "high",
        "tyre_degradation": "low",
        "pit_loss_seconds": 19.0,
        "drs_zones": 1,
        "notes": "Qualifying position dominates the result; strategy is mostly about safety-car timing.",
    },
    "villeneuve": {
        "circuit_type": "hybrid",
        "overtaking_difficulty": "low",
        "tyre_degradation": "medium",
        "pit_loss_seconds": 18.0,
        "drs_zones": 3,
        "notes": "Stop-start layout, heavy braking, frequent safety cars.",
    },
    "catalunya": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "high",
        "tyre_degradation": "high",
        "pit_loss_seconds": 21.0,
        "drs_zones": 2,
        "notes": "Long high-speed corners; aerodynamic efficiency and front-left wear dominate.",
    },
    "red_bull_ring": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "low",
        "tyre_degradation": "medium",
        "pit_loss_seconds": 20.0,
        "drs_zones": 3,
        "notes": "Short lap and traction-limited; small pace gaps produce large lap-time spreads.",
    },
    "silverstone": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "medium",
        "tyre_degradation": "high",
        "pit_loss_seconds": 21.0,
        "drs_zones": 2,
        "notes": "Highest-energy corners on the calendar; weather swings often decide strategy.",
    },
    "hungaroring": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "high",
        "tyre_degradation": "medium",
        "pit_loss_seconds": 20.0,
        "drs_zones": 2,
        "notes": "Twisty and narrow; the undercut is strong because clean air is hard to find.",
    },
    "spa": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "low",
        "tyre_degradation": "medium",
        "pit_loss_seconds": 19.0,
        "drs_zones": 2,
        "notes": "Long lap with big slipstream effects; localised weather is common.",
    },
    "zandvoort": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "high",
        "tyre_degradation": "medium",
        "pit_loss_seconds": 21.0,
        "drs_zones": 2,
        "notes": "Banked corners load tyres unusually; overtaking on track is rare.",
    },
    "monza": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "low",
        "tyre_degradation": "low",
        "pit_loss_seconds": 25.0,
        "drs_zones": 2,
        "notes": "Lowest-downforce race of the year; one-stop is standard and slipstreaming matters.",
    },
    "baku": {
        "circuit_type": "street",
        "overtaking_difficulty": "low",
        "tyre_degradation": "low",
        "pit_loss_seconds": 19.0,
        "drs_zones": 2,
        "notes": "2km straight plus walls: low degradation but very high safety-car probability.",
    },
    "marina_bay": {
        "circuit_type": "street",
        "overtaking_difficulty": "high",
        "tyre_degradation": "medium",
        "pit_loss_seconds": 22.0,
        "drs_zones": 3,
        "notes": "Long, hot and physical; historically one of the highest safety-car rates on the calendar.",
    },
    "americas": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "medium",
        "tyre_degradation": "high",
        "pit_loss_seconds": 21.0,
        "drs_zones": 2,
        "notes": "Bumpy surface and fast esses; graining and ride height are recurring themes.",
    },
    "rodriguez": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "medium",
        "tyre_degradation": "low",
        "pit_loss_seconds": 22.0,
        "drs_zones": 3,
        "notes": "High altitude reduces downforce and cooling; long run to turn 1 shuffles the order.",
    },
    "interlagos": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "low",
        "tyre_degradation": "medium",
        "pit_loss_seconds": 20.0,
        "drs_zones": 2,
        "notes": "Short lap, frequent rain, and a sprint weekend format in recent years.",
    },
    "vegas": {
        "circuit_type": "street",
        "overtaking_difficulty": "low",
        "tyre_degradation": "low",
        "pit_loss_seconds": 20.0,
        "drs_zones": 2,
        "notes": "Cold night running makes tyre warm-up, not wear, the limiting factor.",
    },
    "losail": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "medium",
        "tyre_degradation": "high",
        "pit_loss_seconds": 22.0,
        "drs_zones": 1,
        "notes": "Continuous fast corners; stint lengths have previously been capped for tyre safety.",
    },
    "yas_marina": {
        "circuit_type": "permanent",
        "overtaking_difficulty": "medium",
        "tyre_degradation": "low",
        "pit_loss_seconds": 21.0,
        "drs_zones": 2,
        "notes": "Cooler evening running and low degradation point to a one-stop.",
    },
}


def meta_for(circuit_ref: str) -> CircuitMeta:
    return CIRCUIT_META.get(circuit_ref, {})
