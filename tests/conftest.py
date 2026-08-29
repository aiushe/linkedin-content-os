"""Make repository-local scripts importable without packaging them as an application library."""

import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure() -> None:
    """Keep asynchronous LangSmith transport failures out of the pytest console.

    This changes logging only. In particular, it does not alter LANGSMITH_TRACING, because that
    setting also controls the privacy boundary for profile-memory prompt context.
    """

    logger = logging.getLogger("langsmith")
    logger.setLevel(logging.CRITICAL + 1)
    logger.addHandler(logging.NullHandler())
    logger.propagate = False


@pytest.fixture
def synthetic_corpus(monkeypatch):
    """Point runtime corpus readers at the tracked, fictional development corpus."""

    from agent.mcp_loader import server as mcp_server
    from pipeline import common

    fixture = ROOT / "tests" / "fixtures" / "dev_corpus"
    monkeypatch.setattr(common, "ROOT", fixture)
    monkeypatch.setattr(common, "PRIVATE", fixture / "private")
    monkeypatch.setattr(common, "CORPUS", fixture / "corpus")
    monkeypatch.setattr(common, "INTEL", fixture / "intel")
    monkeypatch.setattr(mcp_server, "ROOT", fixture)
    monkeypatch.setattr(mcp_server, "INTEL", fixture / "intel")
    return fixture
