"""Cheap, structured intake router."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agent import config
from agent.models import CostMeter, get_model, invoke_with_deadline
from agent.state import DraftState


class IntentDecision(BaseModel):
    intent: Literal[
        "authority", "reach", "comment", "profile_rewrite", "outreach", "out_of_scope"
    ]
    confidence: float = Field(ge=0, le=1)
    rationale: str


def _offline_route(idea: str) -> IntentDecision:
    text = idea.strip().lower()
    if len(text.split()) <= 1:
        return IntentDecision(
            intent="authority", confidence=0.2, rationale="Idea is too short to classify safely."
        )
    if any(
        word in text for word in ("book a flight", "flight", "order food", "send money", "weather")
    ):
        return IntentDecision(
            intent="out_of_scope", confidence=0.99, rationale="This is not LinkedIn content work."
        )
    if any(word in text for word in ("comment", "reply", "respond to this post")):
        return IntentDecision(
            intent="comment", confidence=0.9, rationale="The request is a reply/comment."
        )
    if any(word in text for word in ("profile rewrite", "rewrite my profile", "linkedin profile")):
        return IntentDecision(
            intent="profile_rewrite",
            confidence=0.95,
            rationale="The request is a LinkedIn profile rewrite.",
        )
    if any(
        phrase in text
        for phrase in ("outreach", "target map", "hiring manager", "connection request", "applied")
    ):
        return IntentDecision(
            intent="outreach",
            confidence=0.9,
            rationale="The request is for the manual outreach workflow.",
        )
    if any(word in text for word in ("reach", "broad", "how-to", "framework")):
        return IntentDecision(
            intent="reach", confidence=0.78, rationale="The request teaches a broad idea."
        )
    return IntentDecision(
        intent="authority", confidence=0.85, rationale="The request is grounded in personal work."
    )


def intake_router(state: DraftState) -> dict:
    """Classify intent, skipping any model call when a user forced the intent."""

    meter = CostMeter(node="intake_router", model=config.MODEL_ROUTER)
    errors: list[dict] = []
    degradation_reasons: list[str] = []
    forced = state.get("forced_intent")
    if forced:
        decision = IntentDecision(
            intent=forced, confidence=1.0, rationale="Intent selected by reviewer."
        )
        event = meter.record(
            node="intake_router", model="forced", prompt_tokens=0, completion_tokens=0
        )
    elif not config.live_models_enabled():
        decision = _offline_route(state["idea"])
        event = meter.record(
            node="intake_router", model="offline", prompt_tokens=0, completion_tokens=0
        )
    else:
        prompt = (
            "Classify this request for a collaborative LinkedIn drafting tool. "
            "Choose authority for "
            "first-person experience, reach for broad educational content, comment for a reply to "
            "someone else's post, profile_rewrite for a LinkedIn profile rewrite, outreach for "
            "manual post-application target mapping or comments, or out_of_scope. Return low "
            "confidence when ambiguous.\n\n"
            f"Request: {state['idea']}"
        )
        try:
            model = get_model("router", callbacks=[meter])
            response = invoke_with_deadline(
                lambda: model.with_structured_output(IntentDecision).invoke(prompt)
            )
            decision = response
            event = meter.event_or_zero(node="intake_router", model=config.MODEL_ROUTER)
        except Exception as exc:  # model access should not turn into an unsafe route
            decision = IntentDecision(
                intent="authority",
                confidence=0.0,
                rationale=f"Router unavailable: {type(exc).__name__}.",
            )
            event = meter.event_or_zero(node="intake_router", model=config.MODEL_ROUTER)
            errors = [
                {
                    "node": "intake_router",
                    "class": "capability",
                    "message": "Router model unavailable; continuing with a general draft.",
                    "detail": f"{type(exc).__name__}: {exc}"[:300],
                }
            ]
    if decision.confidence < config.ROUTER_CONFIDENCE_FLOOR:
        degradation_reasons.append(
            "Draft direction was uncertain; the system continued with a general LinkedIn draft."
        )
    return {
        "intent": decision.intent,
        "intent_confidence": decision.confidence,
        "router_rationale": decision.rationale,
        "cost_events": [event],
        "errors": errors,
        "degradation_reasons": degradation_reasons,
    }
