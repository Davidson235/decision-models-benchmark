"""Known-answer tests for src/metrics.py. No pytest required:

    python tests/test_metrics.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.metrics import (  # noqa: E402
    accuracy,
    auc,
    binary_brier,
    ece,
    log_loss,
    mae,
    multiclass_brier,
    paired_bootstrap,
    qwk,
    wilson_ci,
)

TOL = 1e-9
failures: list[str] = []


def check(name: str, got, want, tol: float = TOL) -> None:
    ok = abs(got - want) <= tol if isinstance(want, float) else got == want
    print(f"{'ok  ' if ok else 'FAIL'} {name}: got={got} want={want}")
    if not ok:
        failures.append(name)


# Brier -----------------------------------------------------------------------
check("multiclass_brier perfect", multiclass_brier({"a": 1.0, "b": 0.0}, "a"), 0.0)
check("multiclass_brier 0.7/0.3 gold=a", multiclass_brier({"a": 0.7, "b": 0.3}, "a"), 0.18)
check("multiclass_brier 0.7/0.3 gold=b", multiclass_brier({"a": 0.7, "b": 0.3}, "b"), 0.98)
check("multiclass_brier gold missing", multiclass_brier({"a": 0.5, "b": 0.5}, "c"), 1.5)
check("binary_brier 0.9 true", binary_brier(0.9, True), 0.01)
check("binary_brier 0.9 false", binary_brier(0.9, False), 0.81)

# NLL -------------------------------------------------------------------------
check("log_loss 0.5", log_loss(0.5), math.log(2))
check("log_loss 1.0 clipped", log_loss(1.0), -math.log(1 - 1e-12), 1e-9)

# ECE -------------------------------------------------------------------------
# bin 0.9-1.0: conf .95, acc .5 ; bin 0.6-0.7: conf .6, acc 1.0
check("ece 4 samples", ece([0.95, 0.95, 0.6, 0.6], [1, 0, 1, 1]), 0.5 * 0.45 + 0.5 * 0.4)
check("ece perfect calibration", ece([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]), 0.0)
check("ece empty", ece([], []), 0.0)

# Accuracy / CI ---------------------------------------------------------------
check("accuracy 3/4", accuracy([1, 1, 1, 0]), 0.75)
lo, hi = wilson_ci(9, 10)
check("wilson_ci 9/10 lower", lo, 0.5959, 1e-3)
check("wilson_ci 9/10 upper", hi, 0.9821, 1e-3)

# AUC -------------------------------------------------------------------------
check("auc perfect", auc([0.1, 0.4, 0.8, 0.9], [False, False, True, True]), 1.0)
check("auc inverted", auc([0.9, 0.8, 0.4, 0.1], [False, False, True, True]), 0.0)
check("auc all ties", auc([0.5, 0.5, 0.5, 0.5], [False, True, False, True]), 0.5)
check("auc one class", math.isnan(auc([0.1, 0.2], [True, True])), True)

# QWK -------------------------------------------------------------------------
check("qwk perfect", qwk([0, 1, 2, 2], [0, 1, 2, 2], 0, 2), 1.0)
# one ordinal error out of four. Hand-computed: num=0.25, den=1.0 -> kappa=0.75
check("qwk one error", qwk([0, 1, 2, 2], [1, 1, 2, 2], 0, 2), 0.75)
check("mae", mae([0.0, 2.0], [1.0, 1.0]), 1.0)

# Paired bootstrap ------------------------------------------------------------
res = paired_bootstrap([1, 1, 1, 1], [1, 1, 1, 1], n_boot=500)
check("bootstrap identical diff", res["diff"], 0.0)
check("bootstrap identical p", res["p"], 1.0)
res = paired_bootstrap([0, 0, 0, 0, 0, 0, 0, 0], [1, 1, 1, 1, 1, 1, 1, 1], n_boot=500)
check("bootstrap all up diff", res["diff"], 1.0)
check("bootstrap all up p", res["p"], 0.0)

print()
if failures:
    print(f"FAILED: {len(failures)} -> {failures}")
    sys.exit(1)
print("all metric tests passed")
