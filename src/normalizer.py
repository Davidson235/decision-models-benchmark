"""Turn a raw System One response into one canonical record per question.

The wire format has three answer shapes and no single unified field, so every
consumer keeps the same small contract:

    {qid: {"type": "choice"|"noul"|"score",
           "value": <label|probability|float>,
           "probs": {label_or_level: probability},
           "confidence": float|None}}

If a response is malformed the normalizer raises loudly instead of silently
producing zeros, because a silent zero would corrupt every downstream metric.
"""
from __future__ import annotations

import math

PROB_SUM_TOLERANCE = 1e-3
RENORMALIZE_TOLERANCE = 0.02


def _check_sum(qid: str, probs: dict, kind: str) -> tuple[dict, bool, float]:
    """Validate a distribution.

    Some providers round probabilities (Jev returned exactly 0.99 on two tasks).
    A distribution that is off by <= 2% is renormalised and flagged rather than
    rejected: the model did answer, and throwing the answer away would bias the
    benchmark against that model. Anything further off is a real parse failure.
    """
    total = sum(probs.values())
    if abs(total - 1.0) <= PROB_SUM_TOLERANCE:
        return probs, False, total
    if abs(total - 1.0) <= RENORMALIZE_TOLERANCE and total > 0:
        return {k: v / total for k, v in probs.items()}, True, total
    raise NormalizationError(f"{qid}: {kind} probabilities sum to {total:.6f}")


class NormalizationError(ValueError):
    pass


def _as_float(key: str, value) -> tuple:
    try:
        return int(key), float(value)
    except (TypeError, ValueError):
        raise NormalizationError(f"score level {key!r} -> {value!r} is not numeric") from None


def normalize_question(qid: str, block: dict) -> dict:
    if not isinstance(block, dict):
        raise NormalizationError(f"{qid}: answer is not an object: {block!r}")
    qtype = block.get("type")
    if qtype == "noul":
        if "noul" not in block:
            raise NormalizationError(f"{qid}: noul answer without 'noul'")
        p = float(block["noul"])
        if not 0.0 <= p <= 1.0:
            raise NormalizationError(f"{qid}: noul {p} outside [0,1]")
        return {
            "type": "noul",
            "value": p,
            "probs": {"true": p, "false": 1.0 - p},
            "confidence": max(p, 1.0 - p),
        }

    if qtype == "choice":
        probs = block.get("probabilities")
        if not isinstance(probs, dict) or not probs:
            raise NormalizationError(f"{qid}: choice answer without probabilities")
        probs = {str(k): float(v) for k, v in probs.items()}
        probs, renormalized, raw_sum = _check_sum(qid, probs, "choice")
        value = block.get("choice")
        if value is None:
            value = max(probs, key=probs.get)
        if value not in probs:
            raise NormalizationError(f"{qid}: choice {value!r} not in probabilities")
        return {
            "type": "choice",
            "value": str(value),
            "probs": probs,
            "confidence": float(block.get("confidence", probs[str(value)])),
            "renormalized": renormalized,
            "raw_prob_sum": raw_sum,
        }

    if qtype == "score":
        probs_raw = block.get("probabilities") or {}
        probs: dict[int, float] = {}
        for k, v in probs_raw.items():
            level, prob = _as_float(k, v)
            probs[level] = prob
        renormalized, raw_sum = False, 1.0
        if probs:
            probs, renormalized, raw_sum = _check_sum(qid, probs, "score")
            expected = sum(level * p for level, p in probs.items())
        else:
            expected = None
        score = block.get("score", expected)
        if score is None:
            raise NormalizationError(f"{qid}: score answer has neither score nor probabilities")
        legend = {int(k): v for k, v in (block.get("legend") or {}).items()}
        confidence = block.get("confidence")
        return {
            "type": "score",
            "value": float(score),
            "probs": probs,
            "confidence": float(confidence) if confidence is not None else (
                max(probs.values()) if probs else None
            ),
            "legend": legend,
            "renormalized": renormalized,
            "raw_prob_sum": raw_sum,
        }

    if qtype == "box":
        # Image grounding: coordinates as fractions of width/height. The exact
        # nesting is provider-specific, so keep the payload intact instead of
        # forcing it into the probability contract.
        payload = block.get("box", block)
        return {"type": "box", "value": payload, "probs": {}, "confidence": block.get("confidence")}

    raise NormalizationError(f"{qid}: unsupported answer type {qtype!r}")


def normalize(response: dict) -> dict:
    """Return ``{qid: canonical_answer}`` for a 200 response."""
    if not isinstance(response, dict):
        raise NormalizationError("response is not an object")
    answers = response.get("answers")
    if not isinstance(answers, dict) or not answers:
        raise NormalizationError(f"response has no answers: {list(response)[:6]}")
    return {qid: normalize_question(qid, block) for qid, block in answers.items()}


def coverage(expected_qids, got) -> list[str]:
    """qids that were asked for but not returned."""
    return [q for q in expected_qids if q not in got]


def check_numeric_health(answer: dict) -> list[str]:
    """Cheap sanity checks used by the smoke test."""
    issues = []
    if not math.isfinite(float(answer.get("confidence") or 0.0)):
        issues.append("confidence is not finite")
    probs = answer.get("probs") or {}
    if probs and abs(sum(probs.values()) - 1.0) > PROB_SUM_TOLERANCE:
        issues.append("probabilities do not sum to 1")
    return issues
