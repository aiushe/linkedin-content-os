"""Verify the configured models support what the graph actually needs.

The router and critic use .with_structured_output(); the grounding node is a ReAct loop
that binds tools. Open models vary widely in function-calling support, so a model that
chats fine can still break the graph. This probes each capability separately so a failure
names the missing feature instead of surfacing as a mysterious escalate.

    uv run python scripts/probe_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel, Field  # noqa: E402

from agent import config  # noqa: E402
from agent.models import MODEL_BY_ROLE, price_for  # noqa: E402


class Verdict(BaseModel):
    intent: str = Field(description="one of: authority, reach, comment, out_of_scope")
    confidence: float


def probe(role: str, model_id: str) -> None:
    from langchain_openai import ChatOpenAI

    options = {"model": model_id, "temperature": 0}
    if config.LLM_BASE_URL:
        options["base_url"] = config.LLM_BASE_URL
    key = config.llm_api_key()
    if key:
        options["api_key"] = key
    llm = ChatOpenAI(**options)

    print(f"\n{role:8} {model_id}")
    rate = price_for(model_id)
    label = "$%s/$%s per 1M" % rate if rate else "UNPRICED (cost table will omit $)"
    print(f"  {'price':22} {label}")

    try:
        out = llm.invoke("Reply with exactly: pong")
        print(f"  {'plain completion':22} OK ({str(out.content).strip()[:20]!r})")
        usage = getattr(out, "usage_metadata", None)
        print(f"  {'usage reported':22} {'OK' if usage else 'MISSING (token counts will be 0)'}")
    except Exception as exc:
        print(f"  {'plain completion':22} FAIL {type(exc).__name__}: {str(exc)[:120]}")
        return

    try:
        result = llm.with_structured_output(Verdict).invoke(
            "Classify: 'a post about my own career change'. Return intent and confidence."
        )
        print(f"  {'structured output':22} OK ({result.intent!r}, {result.confidence})")
    except Exception as exc:
        print(f"  {'structured output':22} FAIL {type(exc).__name__}: {str(exc)[:120]}")
        print("     -> router and critic need this; pick another model for this role")

    try:
        from langchain_core.tools import tool

        @tool
        def lookup(query: str) -> str:
            """Look something up."""
            return "result"

        bound = llm.bind_tools([lookup]).invoke("Use the lookup tool to find 'agentic product'.")
        calls = getattr(bound, "tool_calls", []) or []
        status = f"OK ({len(calls)} call)" if calls else "NO TOOL CALL EMITTED"
        print(f"  {'tool calling':22} {status}")
        if not calls:
            print("     -> the grounding ReAct node needs this")
    except Exception as exc:
        print(f"  {'tool calling':22} FAIL {type(exc).__name__}: {str(exc)[:120]}")


def main() -> None:
    print(f"endpoint: {config.LLM_BASE_URL or 'https://api.openai.com/v1'}")
    if not config.llm_api_key():
        raise SystemExit(f"No key in ${config.LLM_API_KEY_ENV}")
    for role, model_id in MODEL_BY_ROLE.items():
        probe(role, model_id)
    print(
        "\nRouter and critic need structured output. "
        "The grounding node needs tool calling."
    )


if __name__ == "__main__":
    main()
