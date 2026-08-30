"""Deterministic advisory voice, factual, and confidentiality checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from pipeline import claims, confidential, voice

from . import config

VoiceVerdict = Literal["pass", "revise", "warn"]
GateVerdict = Literal["pass", "warn", "revise"]


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


def _configured_flags(
    result: dict[str, Any], profile: dict[str, Any], *, excluded_features: frozenset[str]
) -> list[dict[str, Any]]:
    """Re-evaluate score flags with the configured z threshold.

    ``pipeline.voice.score_text`` intentionally remains untouched. This wrapper
    preserves its feature extraction and tell detection while making the threshold
    configurable at the harness layer.
    """

    current = result.get("features", {})
    flags: list[dict[str, Any]] = []
    for key, expected in profile.get("features", {}).items():
        if key in excluded_features or key not in current or not isinstance(expected, dict):
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


def safe_voice_score(draft: str, *, target_format: str = "short_post") -> dict[str, Any]:
    """Score voice and report when the fingerprint is not meaningful."""

    profile = voice.load_fingerprint()
    result = dict(voice.score_text(draft, profile))
    excluded_features = (
        config.VOICE_SHORT_POST_EXCLUDED_FEATURES if target_format == "short_post" else frozenset()
    )
    result["flags"] = _configured_flags(result, profile, excluded_features=excluded_features)
    result["banned_tells"] = _dedupe(list(result.get("banned_tells", [])))
    missing_profile = (
        int(profile.get("sample_count") or 0) < config.VOICE_MIN_SAMPLES
        or int(profile.get("word_count") or 0) < config.VOICE_MIN_WORDS
        or not profile.get("features")
    )
    if missing_profile:
        verdict: VoiceVerdict = "warn"
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
            "target_format": target_format,
            "excluded_features": sorted(excluded_features),
            "scored_features": sorted(
                key
                for key in profile.get("features", {})
                if key in result.get("features", {}) and key not in excluded_features
            ),
        }
    )
    return result


def _verdict(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("verdict", "warn"))
    return str(getattr(value, "verdict", "warn"))


def reduce_verdicts(
    voice_report: Any, claims_report: Any, confidential_report: Any | None = None
) -> GateVerdict:
    """Summarize voice readiness without letting any finding block a draft."""

    claim_verdict = _verdict(claims_report)
    voice_verdict = _verdict(voice_report)
    if claim_verdict == "warn" or voice_verdict == "warn":
        return "warn"
    if voice_verdict == "revise":
        return "revise"
    return "pass"


def gate(
    draft: str,
    allowlist: list[claims.AllowedFact] | None = None,
    confidential_terms: set[str] | None = None,
    *,
    target_format: str = "short_post",
) -> GateReport:
    """Run all deterministic gates without a model or network request."""

    voice_report = safe_voice_score(draft, target_format=target_format)
    claims_report = claims.check(draft, allowlist)
    confidential_report = confidential.check(draft, confidential_terms)
    return GateReport(
        verdict=reduce_verdicts(voice_report, claims_report, confidential_report),
        voice=voice_report,
        claims=claims_report,
        confidential=confidential_report,
    )
