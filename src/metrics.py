"""Scoring metrics for typed decision answers.

Every function is pure and side-effect free so that it can be unit tested
against analytically known values.
"""
from __future__ import annotations

import math
import random
from typing import Iterable, Sequence

EPS = 1e-12
NLL_EPS = 1e-6


def clamp(p: float, lo: float = EPS, hi: float = 1.0 - EPS) -> float:
    return max(lo, min(hi, float(p)))


# ---------------------------------------------------------------- Brier / NLL

def multiclass_brier(probs: dict, gold: str) -> float:
    """Sum of squared errors over the label set (probs keys + gold)."""
    keys = set(probs) | {gold}
    return sum((float(probs.get(k, 0.0)) - (1.0 if k == gold else 0.0)) ** 2 for k in keys)


def binary_brier(p: float, y: bool) -> float:
    return (float(p) - (1.0 if y else 0.0)) ** 2


def log_loss(p_true: float) -> float:
    """Negative log-likelihood, clipped at 1e-6.

    A model that assigns exactly zero to the gold label is not infinitely wrong
    in practice; clipping keeps one catastrophic answer from dominating the mean.
    """
    return -math.log(clamp(p_true, lo=NLL_EPS, hi=1.0))


def p_true_binary(p: float, y: bool) -> float:
    """Probability the model assigned to the true label of a yes/no question."""
    return float(p) if y else 1.0 - float(p)


# ----------------------------------------------------------------------- ECE

def ece(confs: Sequence[float], corrects: Sequence[int], bins: int = 10) -> float:
    """Expected calibration error over equal-width confidence bins.

    ``confs`` is the confidence of the chosen answer, ``corrects`` is 1/0.
    """
    n = len(confs)
    if n == 0:
        return 0.0
    if len(corrects) != n:
        raise ValueError("confs and corrects must have the same length")
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [
            i
            for i, c in enumerate(confs)
            if (lo <= c < hi) or (b == bins - 1 and c >= hi)
        ]
        if not idx:
            continue
        acc = sum(corrects[i] for i in idx) / len(idx)
        conf = sum(confs[i] for i in idx) / len(idx)
        total += len(idx) / n * abs(acc - conf)
    return total


def reliability_table(confs: Sequence[float], corrects: Sequence[int], bins: int = 10):
    rows = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [
            i
            for i, c in enumerate(confs)
            if (lo <= c < hi) or (b == bins - 1 and c >= hi)
        ]
        if not idx:
            continue
        rows.append(
            {
                "bin": f"{lo:.1f}-{hi:.1f}",
                "n": len(idx),
                "avg_conf": sum(confs[i] for i in idx) / len(idx),
                "accuracy": sum(corrects[i] for i in idx) / len(idx),
            }
        )
    return rows


# ------------------------------------------------------------ classification

def accuracy(corrects: Sequence[int]) -> float:
    return sum(corrects) / len(corrects) if corrects else 0.0


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def auc(scores: Sequence[float], labels: Sequence[bool]) -> float:
    """ROC AUC with tie handling (Mann-Whitney U)."""
    pairs = list(zip(scores, labels))
    pos = [s for s, y in pairs if y]
    neg = [s for s, y in pairs if not y]
    if not pos or not neg:
        return float("nan")
    # rank-based, average ranks for ties
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    rank_sum_pos = sum(ranks[i] for i, (_, y) in enumerate(pairs) if y)
    n_pos, n_neg = len(pos), len(neg)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def qwk(y_true: Sequence[int], y_pred: Sequence[int], lo: int, hi: int) -> float:
    """Quadratic weighted kappa for an ordinal scale [lo, hi]."""
    k = hi - lo + 1
    if len(y_true) != len(y_pred) or not y_true:
        raise ValueError("empty or mismatched inputs")
    obs = [[0] * k for _ in range(k)]
    for t, p in zip(y_true, y_pred):
        obs[int(t) - lo][int(p) - lo] += 1
    n = sum(sum(row) for row in obs)
    rows = [sum(obs[i]) for i in range(k)]
    cols = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) ** 2) / ((k - 1) ** 2) if k > 1 else 0.0
            num += w * obs[i][j]
            den += w * rows[i] * cols[j] / n
    if den == 0:
        return 1.0
    return 1.0 - num / den


def mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    return sum(abs(a - b) for a, b in zip(y_true, y_pred)) / len(y_true)


# --------------------------------------------------------------- uncertainty

def paired_bootstrap(
    a: Sequence[float],
    b: Sequence[float],
    n_boot: int = 10000,
    seed: int = 20261023,
) -> dict:
    """Bootstrap CI for mean(b) - mean(a) over paired per-task values.

    Returns mean difference, 95% interval and a two-sided p-value for the
    null hypothesis that the difference is zero (fraction of resamples that
    cross zero, doubled).
    """
    if len(a) != len(b):
        raise ValueError("paired inputs must have equal length")
    if not a:
        return {"diff": 0.0, "lo": 0.0, "hi": 0.0, "p": 1.0}
    diffs = [y - x for x, y in zip(a, b)]
    mean = sum(diffs) / len(diffs)
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += diffs[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot) - 1]
    below = sum(1 for m in means if m <= 0) / n_boot
    above = sum(1 for m in means if m >= 0) / n_boot
    p = min(1.0, 2 * min(below, above))
    return {"diff": mean, "lo": lo, "hi": hi, "p": p}


def summarize(values: Iterable[float]) -> dict:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not vals:
        return {"n": 0, "mean": float("nan"), "p50": float("nan"), "p95": float("nan")}
    vals.sort()
    n = len(vals)
    p50 = vals[min(n - 1, int(0.50 * n))]
    p95 = vals[min(n - 1, int(0.95 * n))]
    return {"n": n, "mean": sum(vals) / n, "p50": p50, "p95": p95}
