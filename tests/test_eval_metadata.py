"""Week 4 evaluation metadata contract."""

from __future__ import annotations

from evals.metadata import outcome_metadata, run_config


def test_run_config_has_the_stable_week4_schema() -> None:
    config = run_config(
        {"id": "case-1", "kind": "happy", "intent_expected": "authority"}, "baseline"
    )

    assert config["configurable"] == {"thread_id": "eval-case-1"}
    assert config["run_name"] == "case:case-1"
    assert config["tags"] == ["happy", "authority", "baseline"]
    assert config["metadata"]["dataset_version"] == "v1"
    assert config["metadata"]["offline"] is False
    assert config["metadata"]["prompt_version"] == "w3-baseline"
    assert config["metadata"]["router_prompt_version"] == "w3-baseline"
    assert config["metadata"]["critique_prompt_version"] == "w3-baseline"


def test_outcome_metadata_normalises_errors_and_degradation_reasons() -> None:
    metadata = outcome_metadata(
        {
            "errors": [
                {"node": "ground", "class": "degradable"},
                {"node": "ground", "class": "degradable"},
                {"node": "write", "class": "capability"},
            ],
            "degradation_reasons": ["No story.", "No template."],
        }
    )

    assert metadata == {
        "error_classes": ["capability", "degradable"],
        "error_nodes": ["ground", "write"],
        "degradation_reasons": ["No story.", "No template."],
    }
