"""Tiered model factory and transparent usage-cost accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from langchain_core.callbacks import BaseCallbackHandler

from . import config

ModelRole = Literal["router", "writer", "critic"]
MODEL_BY_ROLE = {
    "router": config.MODEL_ROUTER,
    "writer": config.MODEL_WRITER,
    "critic": config.MODEL_CRITIC,
}

# USD / million tokens. Estimates are deliberately visible and easy to update.
MODEL_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
}


def get_model(role: ModelRole, *, callbacks: list[Any] | None = None) -> Any:
    """Return the configured ChatOpenAI model for a graph role."""

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=MODEL_BY_ROLE[role], temperature=0.2, callbacks=callbacks or [])


def _usage_from(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None and hasattr(response, "llm_output"):
        usage = (response.llm_output or {}).get("token_usage")
    if usage is None and hasattr(response, "response_metadata"):
        usage = response.response_metadata.get("token_usage")
    usage = usage or {}
    return {
        "prompt_tokens": int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0),
        "completion_tokens": int(
            usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
        ),
    }


@dataclass
class CostMeter(BaseCallbackHandler):
    """Collect per-node model usage for state and eval reporting."""

    node: str | None = None
    model: str | None = None
    events: list[dict[str, float | int | str]] = field(default_factory=list)

    def record(
        self,
        *,
        node: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> dict[str, float | int | str]:
        input_rate, output_rate = MODEL_PRICES.get(model, (0.0, 0.0))
        event: dict[str, float | int | str] = {
            "node": node,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "usd": round(
                (prompt_tokens * input_rate + completion_tokens * output_rate) / 1_000_000, 8
            ),
        }
        self.events.append(event)
        return event

    def record_response(
        self, *, node: str, model: str, response: Any
    ) -> dict[str, float | int | str]:
        return self.record(node=node, model=model, **_usage_from(response))

    def on_llm_end(self, response: Any, **_: Any) -> None:
        """LangChain callback hook used by live model nodes."""

        self.record(
            node=self.node or "unknown",
            model=self.model or "unknown",
            **_usage_from(response),
        )

    def event_or_zero(self, *, node: str, model: str) -> dict[str, float | int | str]:
        """Return callback usage, or an explicit zero event for unavailable metadata."""

        return self.events[-1] if self.events else self.record(node=node, model=model)
