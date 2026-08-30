"""Computed observations for the human reviewer, never an automatic editor."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from agent import config
from agent.models import CostMeter, get_model, invoke_with_deadline
from agent.skills import role_block
from agent.state import DraftState


class CritiqueOutput(BaseModel):
    verdict: Literal["pass", "warn", "revise"]
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


def _prompt(state: DraftState) -> str:
    """Critique against deterministic evidence plus the selected authored playbook."""

    prompt = (
        "Produce targeted fixes only from this computed gate report. "
        "Do not invent a new rubric or claim the draft passed.\n\n"
        + str({"voice": state.get("voice_report"), "claims": state.get("claims_report")})
    )
    playbook = role_block(str(state.get("intent") or ""))
    return prompt + (f"\n\nAuthored role playbook:\n{playbook}" if playbook else "")


def critique(state: DraftState) -> dict:
    """Turn deterministic findings into optional, human-visible observations."""

    meter = CostMeter(node="critique", model=config.MODEL_CRITIC)
    if config.live_models_enabled():
        try:
            output = invoke_with_deadline(
                lambda: get_model("critic", callbacks=[meter])
                .with_structured_output(CritiqueOutput)
                .invoke(_prompt(state))
            )
            event = meter.event_or_zero(node="critique", model=config.MODEL_CRITIC)
        except Exception:
            output = _computed_critique(state)
            event = meter.event_or_zero(node="critique", model=config.MODEL_CRITIC)
    else:
        output = _computed_critique(state)
        event = meter.record(node="critique", model="offline")
    return {
        "critique": output.model_dump(),
        "cost_events": [event],
    }
