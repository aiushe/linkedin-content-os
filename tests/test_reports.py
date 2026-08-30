from __future__ import annotations

from scripts import build_reports


def test_top_posts_report_contains_plan_columns():
    report = build_reports.top_posts_report(
        [
            {
                "x_factor": 3.2,
                "engagement": 10,
                "hook": "A source hook",
                "url": "https://example.test/post",
                "image_path": None,
            }
        ]
    )

    assert "| X-factor | Hook | Link | Image path |" in report
    assert "A source hook" in report


def test_template_library_excludes_singletons_and_describes_shape():
    report = build_reports.template_library_report(
        [
            {"template_id": 1, "text": "A short sentence.", "hook": "One"},
            {"template_id": 1, "text": "Another short sentence.", "hook": "Two"},
            {"template_id": 2, "text": "Only one", "hook": "Three"},
        ]
    )

    assert "## Template 1 · 2 posts" in report
    assert "Template 2" not in report
