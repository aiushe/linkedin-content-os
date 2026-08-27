"""Human-gated LangGraph harness for the LinkedIn Content OS."""

__all__ = ["build_graph"]


def build_graph(*args, **kwargs):
    """Lazily import graph assembly to keep MCP gate tools free of import cycles."""

    from .graph import build_graph as _build_graph

    return _build_graph(*args, **kwargs)
