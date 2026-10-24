# Decision Models Benchmark — run-20261023-230946

Generated: `2026-10-23T23:21:13`  
Paired tasks used for pairwise tests: **107**  
Metric definitions: `p_true` is the probability assigned to the gold label; ECE uses 10 equal-width bins over the confidence of the chosen answer.

## 1. Overall

| # | Model | n | Accuracy | 95% CI | Brier ↓ | NLL ↓ | ECE ↓ | p50 ms | p95 ms | Cost $ | Out tok |
|---|-------|---|----------|--------|---------|-------|-------|--------|--------|--------|---------|
| 1 | `baseten/mammoth-1:free` | 107 | **0.972** | 0.92–0.99 | 0.076 | 2.632 | 0.092 | 594 | 1000 | 0 | 107 |
| 2 | `typesafe/jev-1.14` | 107 | **0.944** | 0.88–0.97 | 0.089 | 2.657 | 0.094 | 516 | 750 | 0.0021 | 4437 |
| 3 | `inception/mercury-decide:free` | 107 | **0.935** | 0.87–0.97 | 0.107 | 2.666 | 0.052 | 610 | 1297 | 0 | 107 |
| 4 | `baseten/elephant-1:free` | 107 | **0.897** | 0.83–0.94 | 0.141 | 2.719 | 0.099 | 531 | 593 | 0 | 107 |
| 5 | `perplexity/pplx-decider-flash-v1.2` | 107 | **0.832** | 0.75–0.89 | 0.220 | 2.833 | 0.072 | 515 | 640 | 0.0002 | 107 |

> Accuracy differences below ~10 pp are not resolvable at n≈107; the CI column is the honest precision of each estimate, and section 5 gives paired tests.

## 2. Accuracy by task family

| Family | `mammoth-1:free` | `jev-1.14` | `mercury-decide:free` | `elephant-1:free` | `pplx-decider-flash-v1.2` |
|--------|------|------|------|------|------|
| abstention | 1.000 (9) | 1.000 (9) | 0.889 (9) | 0.778 (9) | 0.667 (9) |
| adversarial | 1.000 (8) | 1.000 (8) | 1.000 (8) | 1.000 (8) | 0.750 (8) |
| choice_fact | 1.000 (12) | 1.000 (12) | 1.000 (12) | 1.000 (12) | 0.917 (12) |
| choice_multiconstraint | 1.000 (8) | 1.000 (8) | 1.000 (8) | 0.875 (8) | 0.750 (8) |
| choice_near_miss | 1.000 (12) | 0.917 (12) | 1.000 (12) | 0.917 (12) | 0.917 (12) |
| choice_shortcut_trap | 1.000 (8) | 1.000 (8) | 1.000 (8) | 0.875 (8) | 0.875 (8) |
| multilingual | 1.000 (14) | 1.000 (14) | 1.000 (14) | 1.000 (14) | 1.000 (14) |
| noul_false | 1.000 (8) | 1.000 (8) | 1.000 (8) | 1.000 (8) | 1.000 (8) |
| noul_true | 1.000 (8) | 1.000 (8) | 0.875 (8) | 1.000 (8) | 1.000 (8) |
| score | 0.850 (20) | 0.750 (20) | 0.750 (20) | 0.700 (20) | 0.600 (20) |

## 3. Calibration

**baseten/mammoth-1:free** — ECE 0.092

| bin | n | avg confidence | accuracy | gap |
|-----|---|----------------|----------|-----|
| 0.2-0.3 | 3 | 0.239 | 0.667 | +0.428 |
| 0.3-0.4 | 2 | 0.371 | 1.000 | +0.629 |
| 0.4-0.5 | 3 | 0.485 | 1.000 | +0.515 |
| 0.5-0.6 | 3 | 0.548 | 0.667 | +0.119 |
| 0.6-0.7 | 4 | 0.626 | 1.000 | +0.374 |
| 0.7-0.8 | 6 | 0.754 | 1.000 | +0.246 |
| 0.8-0.9 | 13 | 0.856 | 1.000 | +0.144 |
| 0.9-1.0 | 73 | 0.978 | 0.986 | +0.008 |

**typesafe/jev-1.14** — ECE 0.094

| bin | n | avg confidence | accuracy | gap |
|-----|---|----------------|----------|-----|
| 0.1-0.2 | 1 | 0.150 | 0.000 | -0.150 |
| 0.2-0.3 | 1 | 0.200 | 1.000 | +0.800 |
| 0.3-0.4 | 1 | 0.350 | 1.000 | +0.650 |
| 0.4-0.5 | 3 | 0.450 | 0.667 | +0.217 |
| 0.5-0.6 | 4 | 0.578 | 0.250 | -0.328 |
| 0.6-0.7 | 5 | 0.654 | 1.000 | +0.346 |
| 0.7-0.8 | 13 | 0.745 | 1.000 | +0.255 |
| 0.8-0.9 | 8 | 0.853 | 1.000 | +0.147 |
| 0.9-1.0 | 71 | 0.983 | 0.986 | +0.003 |

**inception/mercury-decide:free** — ECE 0.052

| bin | n | avg confidence | accuracy | gap |
|-----|---|----------------|----------|-----|
| 0.2-0.3 | 1 | 0.218 | 1.000 | +0.782 |
| 0.3-0.4 | 1 | 0.363 | 1.000 | +0.637 |
| 0.5-0.6 | 2 | 0.590 | 0.500 | -0.090 |
| 0.6-0.7 | 1 | 0.679 | 0.000 | -0.679 |
| 0.7-0.8 | 6 | 0.755 | 0.833 | +0.079 |
| 0.8-0.9 | 4 | 0.853 | 0.750 | -0.103 |
| 0.9-1.0 | 92 | 0.994 | 0.967 | -0.027 |

**baseten/elephant-1:free** — ECE 0.099

| bin | n | avg confidence | accuracy | gap |
|-----|---|----------------|----------|-----|
| 0.0-0.1 | 2 | 0.050 | 0.500 | +0.450 |
| 0.2-0.3 | 3 | 0.251 | 0.000 | -0.251 |
| 0.3-0.4 | 3 | 0.355 | 0.667 | +0.311 |
| 0.4-0.5 | 3 | 0.450 | 0.333 | -0.116 |
| 0.5-0.6 | 9 | 0.573 | 0.778 | +0.204 |
| 0.6-0.7 | 4 | 0.632 | 1.000 | +0.368 |
| 0.7-0.8 | 14 | 0.759 | 0.929 | +0.170 |
| 0.8-0.9 | 9 | 0.854 | 0.889 | +0.035 |
| 0.9-1.0 | 60 | 0.973 | 1.000 | +0.027 |

**perplexity/pplx-decider-flash-v1.2** — ECE 0.072

| bin | n | avg confidence | accuracy | gap |
|-----|---|----------------|----------|-----|
| 0.2-0.3 | 6 | 0.268 | 0.167 | -0.102 |
| 0.3-0.4 | 3 | 0.365 | 0.667 | +0.302 |
| 0.4-0.5 | 7 | 0.451 | 0.286 | -0.165 |
| 0.5-0.6 | 5 | 0.550 | 1.000 | +0.450 |
| 0.6-0.7 | 9 | 0.667 | 0.667 | -0.001 |
| 0.7-0.8 | 11 | 0.764 | 0.818 | +0.054 |
| 0.8-0.9 | 10 | 0.871 | 0.800 | -0.071 |
| 0.9-1.0 | 56 | 0.974 | 1.000 | +0.026 |

## 4. Behavioural diagnostics

| Model | Abstain on unanswerable | False abstain | RU/EN parity | Score MAE | nMAE | Bias |
|-------|------------------------|---------------|--------------|-----------|------|------|
| `baseten/mammoth-1:free` | 1.000 | 0.000 | 1.000 (7 pairs) | 0.290 | 0.104 | -0.11 |
| `typesafe/jev-1.14` | 1.000 | 0.000 | 1.000 (7 pairs) | 0.294 | 0.104 | -0.14 |
| `inception/mercury-decide:free` | 0.889 | 0.000 | 1.000 (7 pairs) | 0.275 | 0.090 | -0.14 |
| `baseten/elephant-1:free` | 0.778 | 0.000 | 1.000 (7 pairs) | 0.417 | 0.151 | -0.19 |
| `perplexity/pplx-decider-flash-v1.2` | 0.667 | 0.000 | 1.000 (7 pairs) | 0.440 | 0.157 | -0.27 |

`Bias` is the mean of `predicted level - gold level` on the 20 score tasks. Every model lands below the rubric by 0.1–0.3 of a level. Two readings fit: the rubric anchors sit one notch higher than the written states justify, or models compress toward the middle of the scale. Note that no gold level in this corpus is 4, so an empty level-4 bin is expected and does not by itself prove central tendency. Treat the score axis as agreement with this rubric, not as an absolute measurement of severity.

| Model | predicted level → count |
|-------|------------------------|
| `baseten/mammoth-1:free` | 0:2, 1:4, 2:10, 3:4 |
| `typesafe/jev-1.14` | 0:2, 1:4, 2:12, 3:2 |
| `inception/mercury-decide:free` | 0:2, 1:4, 2:12, 3:2 |
| `baseten/elephant-1:free` | 0:2, 1:5, 2:9, 3:4 |
| `perplexity/pplx-decider-flash-v1.2` | 0:1, 1:9, 2:8, 3:2 |


## 5. Paired comparison (bootstrap, 2000 resamples)

| Pair (B − A) | Δ accuracy | 95% CI | p |
|--------------|-----------|--------|---|
| baseten/mammoth-1:free vs perplexity/pplx-decider-flash-v1.2 | -0.140 | -0.215 … -0.075 | 0.000 |
| perplexity/pplx-decider-flash-v1.2 vs typesafe/jev-1.14 | +0.112 | +0.047 … +0.178 | 0.000 |
| inception/mercury-decide:free vs perplexity/pplx-decider-flash-v1.2 | -0.103 | -0.168 … -0.037 | 0.006 |
| baseten/elephant-1:free vs baseten/mammoth-1:free | +0.075 | +0.028 … +0.131 | 0.000 |
| baseten/elephant-1:free vs perplexity/pplx-decider-flash-v1.2 | -0.065 | -0.131 … +0.000 | 0.055 |
| baseten/elephant-1:free vs typesafe/jev-1.14 | +0.047 | +0.000 … +0.093 | 0.068 |
| baseten/elephant-1:free vs inception/mercury-decide:free | +0.037 | -0.009 … +0.093 | 0.212 |
| baseten/mammoth-1:free vs inception/mercury-decide:free | -0.037 | -0.075 … -0.009 | 0.036 |
| baseten/mammoth-1:free vs typesafe/jev-1.14 | -0.028 | -0.065 … +0.000 | 0.113 |
| inception/mercury-decide:free vs typesafe/jev-1.14 | +0.009 | -0.019 … +0.037 | 0.800 |

## 6. Reading of the numbers

- Highest raw accuracy: `baseten/mammoth-1:free` at 0.972 (95% CI 0.92–0.99).
- Best calibrated: `inception/mercury-decide:free` with ECE 0.052.
- Cheapest: `baseten/mammoth-1:free` at $0 for the whole suite.
- Fastest p50: `perplexity/pplx-decider-flash-v1.2` at 515 ms.

These four optima do not have to coincide; a model that wins on accuracy may lose on calibration, and the cheapest model may be the best calibrated one. The report keeps the axes separate on purpose — collapsing them into one number is a value judgement, not a measurement.
