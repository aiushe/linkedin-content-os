"""Load this repository's MCP server without colliding with the ``mcp`` SDK package."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def _load_server() -> ModuleType:
    module_name = "linkedin_content_os_mcp_server"
    existing = sys.modules.get(module_name)
    if existing is not None:
        return existing
    path = Path(__file__).resolve().parents[1] / "mcp" / "server.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - impossible in a checked-out repo
        raise ImportError(f"Cannot load local MCP server at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


server = _load_server()
