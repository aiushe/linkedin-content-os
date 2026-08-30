"""Tiered model factory and transparent usage-cost accounting."""

from __future__ import annotations

import json
import os
import signal
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Generator, Literal, TypeVar

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

# Extra rates without editing code, e.g.
#   MODEL_PRICES_JSON='{"Qwen/Qwen3-32B": [0.10, 0.30]}'
for _name, _rate in json.loads(os.getenv("MODEL_PRICES_JSON", "{}")).items():
    MODEL_PRICES[_name] = (float(_rate[0]), float(_rate[1]))

UNKNOWN_PRICE = "unpriced"
T = TypeVar("T")


class ModelDeadlineExceeded(TimeoutError):
    """Raised when a live provider call exceeds the process-enforced deadline."""


@contextmanager
def model_deadline() -> Generator[None, None, None]:
    """Enforce a real deadline when the OpenAI-compatible client ignores its timeout.

    POSIX signals can interrupt a blocking SSL read in the main thread. Other threads retain the
    client timeout, because Python only permits installing this signal handler in the main thread.
    """

    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def expire(_signum: int, _frame: Any) -> None:
        raise ModelDeadlineExceeded(
            f"Model request exceeded {config.LLM_HARD_TIMEOUT_SECONDS:g} seconds."
        )

    previous = signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, config.LLM_HARD_TIMEOUT_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def invoke_with_deadline(operation: Callable[[], T]) -> T:
    with model_deadline():
        return operation()


def price_for(model: str) -> tuple[float, float] | None:
    """None means the model has no known rate. Token counts stay accurate either way.

    Reporting an unpriced model as $0.00 would make a cost table quietly dishonest.
    """

    return MODEL_PRICES.get(model)


def get_model(role: ModelRole, *, callbacks: list[Any] | None = None) -> Any:
    """Return the configured ChatOpenAI model for a graph role."""

    from langchain_openai import ChatOpenAI

    options: dict[str, Any] = {
        "model": MODEL_BY_ROLE[role],
        "temperature": config.WRITER_TEMPERATURE if role == "writer" else 0.2,
        "callbacks": callbacks or [],
        "timeout": config.LLM_TIMEOUT_SECONDS,
        # A request timeout must remain a real upper bound. Retrying a stalled request
        # inside the provider client would multiply that bound before the graph can report it.
        "max_retries": 0,
    }
    if config.LLM_BASE_URL:
        options["base_url"] = config.LLM_BASE_URL
    if config.LLM_SEED is not None:
        options["seed"] = config.LLM_SEED
    key = config.llm_api_key()
    if key:
        options["api_key"] = key
    return ChatOpenAI(**options)


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
