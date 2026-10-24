"""Normalizer tests over recorded wire responses (no network).

    python tests/test_normalizer.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.normalizer import (  # noqa: E402
    NormalizationError,
    coverage,
    normalize,
    normalize_question,
)

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"{'ok  ' if cond else 'FAIL'} {name}{(' -> ' + detail) if detail and not cond else ''}")
    if not cond:
        failures.append(name)


def raises(fn) -> bool:
    try:
        fn()
    except NormalizationError:
        return True
    except Exception:
        return False
    return False


# Real captured responses -----------------------------------------------------
MAMMOTH = {
    "model": "baseten/mammoth-1-20261021",
    "answers": {
        "refund": {"type": "noul", "noul": 0.9994020426058993},
        "team": {
            "type": "choice",
            "choice": "payments",
            "probabilities": {
                "sales": 0.000033847483666034784,
                "tech": 0.0005796940331704157,
                "payments": 0.9993864584831637,
            },
            "confidence": 0.9990796877247453,
        },
        "urg": {
            "type": "score",
            "score": 1.3444137768803939,
            "legend": {
                "0": "Может подождать",
                "1": "На этой неделе",
                "2": "Блокирует работу",
            },
            "probabilities": {
                "0": 0.0878461549702202,
                "1": 0.47989391317916597,
                "2": 0.43225993185061395,
            },
            "confidence": 0.21984086976874873,
        },
    },
    "usage": {"input_tokens": 237, "output_tokens": 3, "cost": 0},
}

SPAN = {
    "model": "respan/span-01-lite-20260925",
    "answers": {"refund": {"type": "noul", "noul": 0.952675}},
    "usage": {"input_tokens": 55, "output_tokens": 0, "cost": 0},
}

answers = normalize(MAMMOTH)
check("three answers parsed", set(answers) == {"refund", "team", "urg"}, str(set(answers)))
check("noul value", abs(answers["refund"]["value"] - 0.9994020426058993) < 1e-12)
check("noul complement", abs(answers["refund"]["probs"]["false"] - (1 - 0.9994020426058993)) < 1e-12)
check("choice label", answers["team"]["value"] == "payments")
check("choice prob lookup", abs(answers["team"]["probs"]["payments"] - 0.9993864584831637) < 1e-12)
check("choice confidence kept", abs(answers["team"]["confidence"] - 0.9990796877247453) < 1e-12)
check("score is float", abs(answers["urg"]["value"] - 1.3444137768803939) < 1e-12)
check("score levels are ints", list(answers["urg"]["probs"]) == [0, 1, 2], str(answers["urg"]["probs"]))
check("score expected value", abs(sum(k * v for k, v in answers["urg"]["probs"].items()) - 1.3444137768803939) < 1e-9)
check("legend preserved", answers["urg"]["legend"][2] == "Блокирует работу")
check("span noul", abs(normalize(SPAN)["refund"]["value"] - 0.952675) < 1e-12)

# Provider rounding: Jev returned exactly 0.99 on two tasks. Must renormalise,
# not reject, and must expose the raw sum so the report can mention it.
rounded = normalize_question("q", {"type": "choice", "choice": "a",
                                  "probabilities": {"a": 0.6, "b": 0.39}})
check("0.99 sum renormalised", rounded["renormalized"] is True)
check("0.99 sum becomes 1", abs(sum(rounded["probs"].values()) - 1.0) < 1e-12)
check("0.99 raw sum preserved", abs(rounded["raw_prob_sum"] - 0.99) < 1e-12)

# Edge cases -----------------------------------------------------------------
check("choice without label falls back to argmax", normalize_question(
    "q", {"type": "choice", "probabilities": {"a": 0.2, "b": 0.8}})["value"] == "b")
check("no answers -> error", raises(lambda: normalize({"model": "x"})))
check("bad prob sum -> error", raises(lambda: normalize_question(
    "q", {"type": "choice", "probabilities": {"a": 0.2, "b": 0.2}})))
check("label not in probs -> error", raises(lambda: normalize_question(
    "q", {"type": "choice", "choice": "z", "probabilities": {"a": 0.5, "b": 0.5}})))
check("noul out of range -> error", raises(lambda: normalize_question("q", {"type": "noul", "noul": 1.5})))
check("unknown type -> error", raises(lambda: normalize_question("q", {"type": "ranking"})))
check("box passes through", normalize_question(
    "q", {"type": "box", "box": {"top": 0.1, "bottom": 0.4,
                                 "left": 0.2, "right": 0.5}})["value"]["top"] == 0.1)
check("score without data -> error", raises(lambda: normalize_question("q", {"type": "score"})))
check("coverage detects missing", coverage(["a", "b"], {"a": 1}) == ["b"])

print()
if failures:
    print(f"FAILED: {len(failures)} -> {failures}")
    sys.exit(1)
print("all normalizer tests passed")
