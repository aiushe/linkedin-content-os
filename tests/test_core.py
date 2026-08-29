from datetime import datetime, timedelta, timezone

from pipeline import common
from pipeline.common import canonical_post, split_frontmatter
from pipeline.voice import aggregate, score_text
from pipeline.xfactor import score_posts


def test_normalization_maps_common_actor_shape():
    post = canonical_post(
        {
            "id": "123",
            "postText": "A useful first line\nSecond line\nThird line\nFourth line",
            "url": "https://www.linkedin.com/posts/example",
            "createdAt": "2026-08-01T10:00:00Z",
            "author": {"publicIdentifier": "ada", "name": "Ada Lovelace", "headline": "Builder"},
            "engagement": {"likes": "1.2K", "comments": 4, "reposts": 2},
        },
        scraped_at="2026-08-02T00:00:00Z",
    )
    assert post["id"] == "linkedin:123"
    assert post["hook"].count("\n") == 2
    assert post["likes"] == 1200
    assert post["engagement"] == 1222
    assert post["author_handle"] == "ada"


def test_normalization_maps_nested_actor_timestamp():
    post = canonical_post(
        {
            "id": "nested-date",
            "content": "A grounded post.",
            "postedAt": {"timestamp": 1_785_456_000, "date": "2026-08-01"},
        }
    )

    assert post["posted_at"] == "2026-07-31T00:00:00Z"


def test_normalization_attributes_a_profile_feed_repost_to_the_watchlist_profile():
    post = canonical_post(
        {
            "id": "repost",
            "content": "A reposted post.",
            "author": {"publicIdentifier": "original-author", "name": "Original Author"},
            "repostedBy": {"publicIdentifier": "watched-profile", "name": "Watched Profile"},
            "query": {"targetUrl": "https://www.linkedin.com/in/watched-profile/"},
        }
    )

    assert post["author_handle"] == "watched-profile"
    assert post["source_profile_handle"] == "watched-profile"
    assert post["original_author_handle"] == "original-author"
    assert post["author_name"] == "Watched Profile"


def test_xfactor_excludes_current_post_and_requires_sample():
    current = datetime(2026, 2, 1, tzinfo=timezone.utc)
    posts = []
    for index in range(10):
        posted = current - timedelta(days=10 - index)
        posts.append(
            {
                "id": str(index),
                "author_handle": "ada",
                "posted_at": posted.isoformat(),
                "likes": 10,
                "comments": 0,
                "shares": 0,
            }
        )
    target = {
        "id": "target",
        "author_handle": "ada",
        "posted_at": current.isoformat(),
        "likes": 50,
        "comments": 0,
        "shares": 0,
    }
    posts.append(target)
    score_posts(posts, minimum_sample=10)
    assert target["author_baseline"] == 10
    assert target["x_factor"] == 5
    assert posts[0]["x_factor"] is None


def test_story_frontmatter_parses_verified_metrics():
    metadata, body = split_frontmatter(
        """---
id: demo
pillars: [apis, product]
metrics:
  - claim: Reduced time
    proof: Dashboard
    verified: true
---

A real story."""
    )
    assert metadata["pillars"] == ["apis", "product"]
    assert metadata["metrics"][0]["verified"] is True
    assert body == "A real story."


def test_voice_score_flags_a_banned_tell_without_fingerprint():
    profile = aggregate(["I shipped the first version. It was messy, then useful."])
    result = score_text("Here's the thing: it's not X, it's Y.", profile)
    assert "here's the thing" in result["banned_tells"]
    assert "it's not X, it's Y" in result["banned_tells"]


def test_private_identity_and_story_bank_take_precedence(tmp_path, monkeypatch):
    private = tmp_path / "private"
    corpus = tmp_path / "corpus"
    (private / "identity").mkdir(parents=True)
    (corpus / "identity").mkdir(parents=True)
    (private / "identity" / "truth-table.md").write_text("private truth", encoding="utf-8")
    (corpus / "identity" / "truth-table.md").write_text("template truth", encoding="utf-8")
    (private / "stories").mkdir()
    (private / "stories" / "local-story.md").write_text(
        "---\nid: local-story\ntitle: Local only\nmetrics: []\n---\nPrivate story.",
        encoding="utf-8",
    )
    monkeypatch.setattr(common, "PRIVATE", private)
    monkeypatch.setattr(common, "CORPUS", corpus)
    monkeypatch.setattr(common, "ROOT", tmp_path)
    assert common.identity_file("truth-table.md").read_text(encoding="utf-8") == "private truth"
    assert common.load_stories()[0]["path"] == "private/stories/local-story.md"
