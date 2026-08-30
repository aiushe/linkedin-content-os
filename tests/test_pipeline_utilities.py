from __future__ import annotations

from pathlib import Path

from pipeline import index_corpus, pull_profile, scrape, selfmetrics, voicediff


def test_pull_profile_render_flattens_nested_values():
    rendered = pull_profile.render(
        {
            "firstName": "Test",
            "lastName": "Person",
            "location": {"parsed": {"text": "Somewhere"}},
            "experience": [{"position": "Builder", "companyName": "Example"}],
        }
    )

    assert "# Current LinkedIn profile" in rendered
    assert "Somewhere" in rendered
    assert "Builder - Example" in rendered


def test_index_corpus_builds_safe_metadata(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        index_corpus,
        "load_stories",
        lambda: [{"id": "story", "title": "A story", "metrics": [{"verified": True}]}],
    )
    destination = tmp_path / "story-index.json"

    index_corpus.build_index(destination)

    assert '"has_verified_metric": true' in destination.read_text(encoding="utf-8")


def test_scrape_uses_header_token_and_normalises_actor_route(monkeypatch):
    seen = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [{"id": "result"}]

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, payload=json, timeout=timeout)
        return Response()

    monkeypatch.setattr(scrape.requests, "post", fake_post)

    assert scrape.run_actor("owner/actor", {"posts": 1}, "secret") == [{"id": "result"}]
    assert "/owner~actor/" in seen["url"]
    assert seen["headers"]["Authorization"] == "Bearer secret"


def test_selfmetrics_uses_only_explicitly_flagged_posts():
    posts = [
        {"is_mine": False, "posted_at": "2026-01-02"},
        {"is_mine": True, "posted_at": "2026-01-01", "hook": "Mine"},
    ]

    assert selfmetrics.my_posts(posts) == [posts[1]]
    assert "Mine" in selfmetrics.report(posts)


def test_voicediff_is_review_only_and_does_not_write(tmp_path: Path):
    generated = tmp_path / "generated.md"
    published = tmp_path / "published.md"
    generated.write_text("Draft line.\n", encoding="utf-8")
    published.write_text("Edited line.\n", encoding="utf-8")

    result = voicediff.compare(generated, published)

    assert "# Edit analysis" in result
    assert "Edited line." in result
