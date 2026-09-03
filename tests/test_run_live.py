"""Focused unit checks for the private Week 4 live runner."""

from __future__ import annotations

import json

from evals import run_live


def test_case_payload_accepts_direct_and_nested_dataset_inputs() -> None:
    case = {"id": "case-1", "idea": "A grounded idea."}
    assert run_live._case_payload(case) == case
    assert run_live._case_payload({"case": case}) == case


def test_dataset_sha_is_stable_for_exact_file_bytes(tmp_path) -> None:
    source = tmp_path / "cases.jsonl"
    source.write_text('{"id":"case-1"}\n', encoding="utf-8")
    first = run_live.dataset_sha256(source)
    assert first == run_live.dataset_sha256(source)
    source.write_text(json.dumps({"id": "case-1"}) + "\n", encoding="utf-8")
    assert first != run_live.dataset_sha256(source)


def test_cost_usd_uses_only_structured_events() -> None:
    assert run_live._cost_usd([{"usd": 0.01}, {"usd": "0.02"}, "ignored"]) == 0.03
