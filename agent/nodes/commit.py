"""The sole write node, reachable only after a human approval interrupt."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from agent.state import DraftState
from pipeline import common


def _title(value: str) -> str:
    first_line = next(
        (line.strip("# ").strip() for line in value.splitlines() if line.strip()), "Draft"
    )
    return first_line[:100]


def _claim_observations(claims: list[object]) -> list[dict[str, object]]:
    """Keep the detector's span, kind, sentence, and line number with a saved draft."""

    return [
        {
            key: claim.get(key)
            for key in ("span", "kind", "sentence", "line_no")
            if key in claim
        }
        for claim in claims
        if isinstance(claim, dict)
    ]


def _grounded_claim_observations(claims_report: object) -> list[dict[str, object]]:
    """Flatten a claim-to-evidence pair into frontmatter-safe observation records."""

    if not isinstance(claims_report, dict):
        return []
    observations: list[dict[str, object]] = []
    for pair in claims_report.get("matched", []):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        claim, fact = pair
        if not isinstance(claim, dict) or not isinstance(fact, dict):
            continue
        observations.append(
            {
                **_claim_observations([claim])[0],
                "evidence_claim": fact.get("claim"),
                "evidence_source": fact.get("source"),
                "evidence_reference": fact.get("source_ref"),
            }
        )
    return observations


def commit(state: DraftState) -> dict:
    """Write a review artifact only after explicit human approval."""

    if state.get("decision") != "approve":
        return {"terminal_reason": "Draft was not saved because approval was not received."}
    claims_report = state.get("claims_report", {})
    unresolved_claims = (
        list(claims_report.get("unresolved", [])) if isinstance(claims_report, dict) else []
    )
    unresolved_spans = []
    for claim in unresolved_claims:
        if not isinstance(claim, dict):
            continue
        span = str(claim.get("span") or "").strip()
        if span and span not in unresolved_spans:
            unresolved_spans.append(span)
    now = datetime.now(timezone.utc)
    title = _title(state.get("draft", ""))
    date = now.date().isoformat()
    stem = f"{date}-{common.slugify(title)[:60]}"
    destination = common.ROOT / "drafts" / "queue" / f"{stem}.md"
    suffix = 2
    while destination.exists():
        destination = common.ROOT / "drafts" / "queue" / f"{stem}-{suffix}.md"
        suffix += 1
    stories = state.get("stories", [])
    story_ids = [str(story["id"]) for story in stories if story.get("id")]
    first_story = next(iter(stories), {})
    pillars = first_story.get("pillars") if isinstance(first_story.get("pillars"), list) else []
    template = state.get("template") or {}
    template_id = template.get("template_id") if isinstance(template, dict) else None
    claims_verdict = str(claims_report.get("verdict", "warn"))
    voice_verdict = str(state.get("voice_report", {}).get("verdict", "warn"))
    confidential_verdict = str(state.get("confidential_report", {}).get("verdict", "warn"))
    review_notes = [
        f"- Claims check: {claims_verdict}.",
        f"- Voice check: {voice_verdict}.",
        "- Image brief / attribution: human review required.",
    ]
    if unresolved_spans:
        review_notes.append(
            "- Unresolved claims remain visible: " + ", ".join(unresolved_spans) + "."
        )
    review_notes += [
        f"- Degraded grounding: {reason}" for reason in state.get("degradation_reasons", [])
    ]
    review_notes += [
        f"- Reviewer annotation: {note}"
        for note in state.get("critique", {}).get("annotations", [])
    ]
    frontmatter = [
        "---",
        f"title: {json.dumps(title)}",
        "status: review",
        f"type: {state.get('intent', 'authority')}",
        f"pillar: {json.dumps(pillars[0] if pillars else '')}",
        f"story_ids: {json.dumps(story_ids)}",
        f"template_id: {json.dumps(template_id)}",
        "claims_checked: true",
        f"claims_verdict: {claims_verdict}",
        f"unresolved_claim_spans: {json.dumps(unresolved_spans)}",
        f"voice_check: {voice_verdict}",
        f"confidential_terms_check: {confidential_verdict}",
        f"observations_claims_grounded: {json.dumps(_grounded_claim_observations(claims_report))}",
        f"observations_claims_not_grounded: {json.dumps(_claim_observations(unresolved_claims))}",
        f"observations_voice: {json.dumps(state.get('voice_report', {}))}",
        f"observations_confidential: {json.dumps(state.get('confidential_report', {}))}",
        f"observations_market: {json.dumps(state.get('market_brief', {}))}",
        f"created_at: {now.isoformat()}",
        "---",
        "",
        f"# {title}",
        "",
        state.get("draft", "").strip(),
        "",
        "## Hook variants",
        "",
    ]
    frontmatter += [
        f"{index}. {hook}" for index, hook in enumerate(state.get("hooks", []), start=1)
    ]
    frontmatter += ["", "## Review notes", "", *review_notes, ""]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(frontmatter), encoding="utf-8")
    return {
        "queue_path": str(destination.relative_to(common.ROOT)),
        "terminal_reason": "Queued for review.",
    }
