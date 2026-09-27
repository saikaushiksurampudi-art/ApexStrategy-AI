"""Amazon Bedrock client for the AI Race Analyst.

Uses the ``bedrock-runtime`` Converse API, which gives one request shape across
model families. The system prompt is deliberately strict: the model is given a
JSON context pack and told that it may not state any fact absent from it.

If Bedrock is disabled or unavailable, callers fall back to
``app.services.narrator``, which writes the same answers from templates. The
product therefore degrades in fluency, never in accuracy.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Race Analyst for ApexStrategy AI, a Formula 1 \
analytics product.

You will receive a JSON object called CONTEXT containing statistics retrieved \
from the application's own database, plus a list of citations describing where \
each block came from.

Rules you must follow without exception:

1. Use ONLY the numbers and facts present in CONTEXT. You have background \
knowledge about Formula 1, but you must not state any fact, statistic, result \
or date that does not appear in CONTEXT.
2. If CONTEXT does not contain what the user asked for, say plainly which part \
you cannot answer and what data would be needed. Never estimate a missing \
statistic.
3. Quote specific numbers and name the seasons, races or sample sizes they come \
from. "Verstappen won 4 of the 9 races here between 2021 and 2025" is good; \
"Verstappen is strong here" is not.
4. Model outputs are probabilities, not forecasts. Describe them as estimates, \
state the key factors behind them, and never imply an outcome is certain. If \
CONTEXT includes model evaluation scores, you may mention how the model \
compares with its baseline.
5. Anything marked as a simulation or scenario is hypothetical. Say so.
6. Note relevant limitations: small sample sizes, regulation changes between \
seasons, missing weather data, or a projected rather than actual starting grid.
7. Be concise and readable for an informed fan. Use short paragraphs, and a \
short bulleted list when comparing things. No preamble, no sign-off.

Write in plain prose. Do not output JSON."""


class BedrockUnavailable(RuntimeError):
    """Raised when Bedrock cannot be reached or is switched off."""


def is_enabled() -> bool:
    return bool(settings.enable_bedrock)


def _runtime_client():
    try:
        import boto3

        return boto3.client("bedrock-runtime", region_name=settings.aws_region)
    except Exception as exc:  # pragma: no cover - depends on environment
        raise BedrockUnavailable(f"boto3 bedrock-runtime unavailable: {exc}") from exc


def _trim(context: Dict[str, Any], max_chars: int = 18000) -> str:
    """Serialise the context pack, shedding the bulkiest blocks if oversized."""
    payload = json.dumps(context, default=str)
    if len(payload) <= max_chars:
        return payload

    trimmed = json.loads(payload)
    facts = trimmed.get("facts", {})
    # Timelines and per-race lists are the usual culprits; summarise them.
    for key in ("timeline", "races", "winners"):
        for block in facts.values():
            if isinstance(block, dict) and key in block and isinstance(block[key], list):
                original = len(block[key])
                block[key] = block[key][-12:]
                block[f"{key}_truncated_from"] = original
    if "head_to_head" in facts and isinstance(facts["head_to_head"], dict):
        timeline = facts["head_to_head"].get("timeline", [])
        if len(timeline) > 12:
            facts["head_to_head"]["timeline"] = timeline[-12:]
            facts["head_to_head"]["timeline_truncated_from"] = len(timeline)

    payload = json.dumps(trimmed, default=str)
    return payload[:max_chars] if len(payload) > max_chars else payload


def generate(
    question: str,
    context: Dict[str, Any],
    history: Optional[List[Dict[str, str]]] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Ask Bedrock to answer ``question`` using only ``context``.

    Returns the answer text and a metadata dict (model id, latency, token
    usage). Raises :class:`BedrockUnavailable` so the caller can fall back.
    """
    if not is_enabled():
        raise BedrockUnavailable("Bedrock is disabled (set ENABLE_BEDROCK=true)")

    client = _runtime_client()

    messages: List[Dict[str, Any]] = []
    for turn in (history or [])[-6:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": [{"text": content}]})

    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        f"CONTEXT:\n{_trim(context)}\n\n"
                        f"USER QUESTION:\n{question}\n\n"
                        "Answer using only CONTEXT."
                    )
                }
            ],
        }
    )

    started = time.monotonic()
    try:
        response = client.converse(
            modelId=settings.bedrock_model_id,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            inferenceConfig={
                "maxTokens": settings.bedrock_max_tokens,
                "temperature": settings.bedrock_temperature,
            },
        )
    except Exception as exc:  # pragma: no cover - depends on AWS
        raise BedrockUnavailable(f"Bedrock converse failed: {exc}") from exc

    latency_ms = int((time.monotonic() - started) * 1000)
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    text = "\n".join(block.get("text", "") for block in blocks).strip()
    if not text:
        raise BedrockUnavailable("Bedrock returned an empty response")

    usage = response.get("usage", {})
    return text, {
        "generator": "bedrock",
        "model_id": settings.bedrock_model_id,
        "latency_ms": latency_ms,
        "input_tokens": usage.get("inputTokens"),
        "output_tokens": usage.get("outputTokens"),
        "stop_reason": response.get("stopReason"),
    }


def health() -> Dict[str, Any]:
    """Report whether the Bedrock path is usable, without spending tokens."""
    if not is_enabled():
        return {
            "enabled": False,
            "reachable": False,
            "detail": "ENABLE_BEDROCK is false; using the template narrator.",
        }
    try:
        _runtime_client()
        return {
            "enabled": True,
            "reachable": True,
            "model_id": settings.bedrock_model_id,
            "region": settings.aws_region,
        }
    except BedrockUnavailable as exc:
        return {"enabled": True, "reachable": False, "detail": str(exc)}
