"""Deterministic, fail-closed voice, factual, and confidentiality gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from pipeline import claims, confidential, voice

from . import config

VoiceVerdict = Literal["pass", "revise", "indeterminate"]
GateVerdict = Literal["pass", "revise", "block", "indeterminate"]


@dataclass
class GateReport:
    verdict: GateVerdict
    voice: dict[str, Any]
    claims: claims.ClaimsReport
    confidential: confidential.ConfidentialTermsReport

    def as_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "voice": self.voice,
            "claims": asdict(self.claims),
            "confidential": asdict(self.confidential),
        }


def _dedupe(values: list[str]) -> list[str]:
    """Deduplicate tells case-insensitively while preserving the first label."""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.lower().strip().replace("openers", "opener")
        if key and key not in seen:
            result.append(value)
            seen.add(key)
    return result


def _configured_flags(result: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-evaluate score flags with the configured z threshold.

    ``pipeline.voice.score_text`` intentionally remains untouched. This wrapper
    preserves its feature extraction and tell detection while making the threshold
    configurable at the harness layer.
    """

    current = result.get("features", {})
    flags: list[dict[str, Any]] = []
    for key, expected in profile.get("features", {}).items():
        if key not in current or not isinstance(expected, dict):
            continue
        mean = expected.get("mean", 0)
        stdev = expected.get("stdev", 0)
        if stdev and abs(float(current[key]) - float(mean)) > config.VOICE_Z_THRESHOLD * float(
            stdev
        ):
            flags.append(
                {
                    "feature": key,
                    "actual": current[key],
                    "expected_mean": mean,
                    "expected_stdev": stdev,
                }
            )
    return flags


def safe_voice_score(draft: str) -> dict[str, Any]:
    """Score voice and refuse to pass when the fingerprint is not meaningful."""

    profile = voice.load_fingerprint()
    result = dict(voice.score_text(draft, profile))
    result["flags"] = _configured_flags(result, profile)
    result["banned_tells"] = _dedupe(list(result.get("banned_tells", [])))
    missing_profile = (
        int(profile.get("sample_count") or 0) < config.VOICE_MIN_SAMPLES
        or int(profile.get("word_count") or 0) < config.VOICE_MIN_WORDS
        or not profile.get("features")
    )
    if missing_profile:
        verdict: VoiceVerdict = "indeterminate"
        reasons = [
            "Voice fingerprint is not ready: add at least "
            f"{config.VOICE_MIN_SAMPLES} samples and {config.VOICE_MIN_WORDS} words."
        ]
    elif result["flags"] or result["banned_tells"]:
        verdict = "revise"
        reasons = ["Draft differs materially from the measured voice profile."]
    else:
        verdict = "pass"
        reasons = []
    result.update(
        {
            "verdict": verdict,
            "reasons": reasons,
            "passes_deterministic_gate": verdict == "pass",
            "profile_sample_count": int(profile.get("sample_count") or 0),
            "profile_word_count": int(profile.get("word_count") or 0),
        }
    )
    return result


def _verdict(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("verdict", "indeterminate"))
    return str(getattr(value, "verdict", "indeterminate"))


def reduce_verdicts(
    voice_report: Any, claims_report: Any, confidential_report: Any | None = None
) -> GateVerdict:
    """Reduce component verdicts with factual and confidentiality blocks first."""

    claim_verdict = _verdict(claims_report)
    confidential_verdict = _verdict(confidential_report or {"verdict": "pass"})
    voice_verdict = _verdict(voice_report)
    if claim_verdict == "block" or confidential_verdict == "block":
        return "block"
    if (
        claim_verdict == "indeterminate"
        or confidential_verdict == "indeterminate"
        or voice_verdict == "indeterminate"
    ):
        return "indeterminate"
    if voice_verdict == "revise":
        return "revise"
    return "pass"


def gate(
    draft: str,
    allowlist: list[claims.AllowedFact] | None = None,
    confidential_terms: set[str] | None = None,
) -> GateReport:
    """Run all deterministic gates without a model or network request."""

    voice_report = safe_voice_score(draft)
    claims_report = claims.check(draft, allowlist)
    confidential_report = confidential.check(draft, confidential_terms)
    return GateReport(
        verdict=reduce_verdicts(voice_report, claims_report, confidential_report),
        voice=voice_report,
        claims=claims_report,
        confidential=confidential_report,
    )
