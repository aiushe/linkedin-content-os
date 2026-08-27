"""Computed-rubric critique node, never a free-form quality judge."""

from __future__ import annotations

from pydantic import BaseModel

from agent import config
from agent.models import CostMeter, get_model
from agent.state import DraftState


class CritiqueOutput(BaseModel):
    verdict: str
    reasons: list[str]
    targeted_fixes: list[str]


def _computed_critique(state: DraftState) -> CritiqueOutput:
    voice_report = state.get("voice_report", {})
    claims_report = state.get("claims_report", {})
    fixes = [
        f"Adjust {item['feature']} toward {item['expected_mean']}."
        for item in voice_report.get("flags", [])
    ]
    fixes += [
        f"Remove or rewrite banned tell: {tell}." for tell in voice_report.get("banned_tells", [])
    ]
    fixes += [
        f"Remove the ungrounded claim {claim['span']!r}; do not replace it with another number."
        for claim in claims_report.get("unmatched", [])
    ]
    return CritiqueOutput(
        verdict=state.get("gate_verdict", "revise"),
        reasons=list(voice_report.get("reasons", [])),
        targeted_fixes=fixes or ["Keep all statements within the retrieved evidence."],
    )


def critique(state: DraftState) -> dict:
    """Turn deterministic gate findings into specific writer instructions."""

    meter = CostMeter(node="critique", model=config.MODEL_CRITIC)
    if config.live_models_enabled():
        prompt = (
            "Produce targeted fixes only from this computed gate report. "
            "Do not invent a new rubric or claim the draft passed.\n\n"
            + str({"voice": state.get("voice_report"), "claims": state.get("claims_report")})
        )
        try:
            output = (
                get_model("critic", callbacks=[meter])
                .with_structured_output(CritiqueOutput)
                .invoke(prompt)
            )
            event = meter.event_or_zero(node="critique", model=config.MODEL_CRITIC)
        except Exception:
            output = _computed_critique(state)
            event = meter.event_or_zero(node="critique", model=config.MODEL_CRITIC)
    else:
        output = _computed_critique(state)
        event = meter.record(node="critique", model="offline")
    revision = int(state.get("revision") or 0) + 1
    errors = []
    if revision > config.MAX_REVISIONS:
        errors.append(
            {
                "node": "critique",
                "class": "loop",
                "message": "Revision cap reached without a passing deterministic gate.",
                "detail": f"max_revisions={config.MAX_REVISIONS}",
            }
        )
    return {
        "critique": output.model_dump(),
        "revision": revision,
        "cost_events": [event],
        "errors": errors,
    }
