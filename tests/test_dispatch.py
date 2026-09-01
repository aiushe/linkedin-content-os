"""Tests for the human-gated post dispatch pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pytest

from pipeline import dispatch


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(dispatch, "ROOT", tmp_path)
    monkeypatch.setattr(dispatch, "QUEUE_DIR", tmp_path / "drafts" / "queue")
    monkeypatch.setattr(dispatch, "APPROVED_DIR", tmp_path / "drafts" / "approved")
    monkeypatch.setattr(dispatch, "PUBLISHED_DIR", tmp_path / "drafts" / "published")
    monkeypatch.setattr(dispatch, "DISPATCH_LOG", tmp_path / "ops" / "dispatch-log.json")

    queue = tmp_path / "drafts" / "queue"
    queue.mkdir(parents=True)
    (tmp_path / "drafts" / "approved").mkdir(parents=True)
    (tmp_path / "drafts" / "published").mkdir(parents=True)
    (tmp_path / "ops").mkdir(parents=True)
    return tmp_path


def _write_draft(workspace: Path, name: str = "2026-08-30-test-draft.md") -> Path:
    draft = workspace / "drafts" / "queue" / name
    draft.write_text(
        '---\ntitle: "Test Draft"\nstatus: review\ntype: authority\n'
        "claims_verdict: pass\nvoice_check: pass\n"
        "confidential_terms_check: pass\nunresolved_claim_spans: []\n"
        'created_at: 2026-08-30T12:00:00Z\n---\n\n# Test Draft\n\n'
        "Here is the post body.\n\nIt has multiple lines.\n\n"
        "## Hook variants\n\n1. Hook one\n2. Hook two\n\n"
        "## Review notes\n\n- Claims check: pass.\n",
        encoding="utf-8",
    )
    return draft


def test_list_shows_queue_drafts(workspace: Path) -> None:
    _write_draft(workspace)
    drafts = dispatch.list_drafts()
    assert len(drafts) == 1
    assert drafts[0]["title"] == "Test Draft"
    assert drafts[0]["claims_verdict"] == "pass"


def test_list_ignores_gitkeep(workspace: Path) -> None:
    (workspace / "drafts" / "queue" / ".gitkeep").touch()
    assert dispatch.list_drafts() == []


def test_preview_parses_frontmatter(workspace: Path) -> None:
    draft = _write_draft(workspace)
    info = dispatch.preview(draft)
    assert info["title"] == "Test Draft"
    assert "Here is the post body." in info["draft_text"]
    assert "Hook one" in info["hooks"]
    assert "Hook two" in info["hooks"]
    assert info["claims_verdict"] == "pass"


def test_preview_strips_title_heading(workspace: Path) -> None:
    draft = _write_draft(workspace)
    info = dispatch.preview(draft)
    assert not info["draft_text"].startswith("# ")


def test_send_requires_env_vars(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = _write_draft(workspace)
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    monkeypatch.delenv("LINKEDIN_LI_AT_COOKIE", raising=False)
    result = dispatch.send(draft)
    assert "error" in result
    assert "APIFY_API_TOKEN" in result["error"]


def test_send_requires_cookie(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = _write_draft(workspace)
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.delenv("LINKEDIN_LI_AT_COOKIE", raising=False)
    result = dispatch.send(draft)
    assert "error" in result
    assert "LINKEDIN_LI_AT_COOKIE" in result["error"]


def test_send_moves_draft_to_published(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = _write_draft(workspace)
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("LINKEDIN_LI_AT_COOKIE", "test-cookie")
    monkeypatch.setenv("APIFY_POST_ACTOR_ID", "test/actor")

    with mock.patch.object(dispatch, "_post_via_apify", return_value={"status": "ok"}):
        result = dispatch.send(draft)

    assert "error" not in result
    assert result["published"].startswith("drafts/published/")
    assert not draft.exists()
    published = workspace / result["published"]
    assert published.exists()
    text = published.read_text(encoding="utf-8")
    assert "status: published" in text
    assert "dispatched_at:" in text


def test_daily_limit_enforced(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = _write_draft(workspace)
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("LINKEDIN_LI_AT_COOKIE", "test-cookie")
    monkeypatch.setenv("DISPATCH_DAILY_LIMIT", "1")

    from pipeline.common import utc_now

    log = [{"date": utc_now(), "draft": "test", "title": "test", "type": "authority"}]
    (workspace / "ops" / "dispatch-log.json").write_text(json.dumps(log), encoding="utf-8")

    result = dispatch.send(draft)
    assert "error" in result
    assert "Daily dispatch limit" in result["error"]


def test_send_logs_dispatch(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = _write_draft(workspace)
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("LINKEDIN_LI_AT_COOKIE", "test-cookie")

    with mock.patch.object(dispatch, "_post_via_apify", return_value={"status": "ok"}):
        dispatch.send(draft)

    log = json.loads((workspace / "ops" / "dispatch-log.json").read_text(encoding="utf-8"))
    assert len(log) == 1
    assert log[0]["title"] == "Test Draft"


def test_cookie_not_in_logs(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = _write_draft(workspace)
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("LINKEDIN_LI_AT_COOKIE", "secret-session-value")

    with mock.patch.object(dispatch, "_post_via_apify", return_value={"status": "ok"}):
        dispatch.send(draft)

    log_text = (workspace / "ops" / "dispatch-log.json").read_text(encoding="utf-8")
    assert "secret-session-value" not in log_text

    published_dir = workspace / "drafts" / "published"
    for path in published_dir.glob("*.md"):
        assert "secret-session-value" not in path.read_text(encoding="utf-8")


def test_empty_draft_rejected(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    draft = workspace / "drafts" / "queue" / "empty.md"
    draft.write_text(
        "---\ntitle: Empty\nstatus: review\ntype: authority\n---\n\n# Empty\n\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("APIFY_API_TOKEN", "test-token")
    monkeypatch.setenv("LINKEDIN_LI_AT_COOKIE", "test-cookie")
    result = dispatch.send(draft)
    assert "error" in result
    assert "empty" in result["error"].lower()
