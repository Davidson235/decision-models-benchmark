# Decision Models Benchmark

[English](README.md) | [Русский](README.ru.md)

An empirical, reproducible benchmark for **System One / Decision Models** across both **Cloud APIs** (OpenRouter, Respan) and **Local Deployment** via `llama.cpp`.

Unlike standard generative LLMs, decision models are specialized routing and classification engines designed to return calibrated probabilities over a discrete set of options in a single forward pass. This benchmark evaluates their argmax accuracy, probability calibration (Brier score, ECE), latency, and cost across **107 Text Tasks** and **20 Vision Ladder Tasks**.

---

## 🖥️ Testbed Hardware Specifications

All local models were evaluated directly on consumer-grade hardware under an explicit **≤ 8 GB VRAM budget constraint**:

| Component | Specification |
|---|---|
| **GPU** | **NVIDIA GeForce RTX 2060 SUPER** (8,192 MiB GDDR6, Driver 581.80, CUDA 12.4) |
| **CPU** | **Intel Core i5-14600KF** (14 cores: 6P + 8E, 20 threads, up to 5.3 GHz) |
| **RAM** | **48 GB** (System RAM) |
| **OS** | **Windows 10 x64** |
| **Local Runtime** | `llama.cpp` (CUDA 12 build, `llama-server.exe` with `-ngl 99` full GPU layer offload) |
| **Budget Ceiling** | **Strict ≤ 8 GB VRAM** (Quantized Q4_K_M / Q8_0; no system RAM paging) |

> **Why the 8 GB limit?**  
> Enterprise benchmarks typically run on 80 GB A100/H100 clusters. This benchmark evaluates whether decision models can deliver fast, private, zero-marginal-cost edge decisions on standard desktop hardware without requiring expensive cloud infrastructure.

---

## 📊 Summary of Results

### 1. Text Benchmark (107 Tasks)

Evaluated across 10 semantic and structural categories (factual choice, near-miss distractors, multi-constraint satisfaction, shortcut traps, adversarial injections, binary predicates, ordinal scoring rubrics, and multilingual Russian/English pairs).

| Model | Environment | Tasks | Accuracy | 95% CI | Brier | ECE | Latency (p50) | Resource / Cost |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **baseten/mammoth-1:free** | Cloud | 107 | **97.2%** | [93.5% … 99.1%] | 0.053 | 0.038 | 884 ms | $0.0000 |
| **typesafe/jev-1.14** | Cloud | 107 | **93.5%** | [88.8% … 97.2%] | 0.117 | 0.061 | 575 ms | $0.0134 |
| **inception/mercury-decide:free** | Cloud | 107 | **90.7%** | [85.0% … 95.3%] | 0.147 | 0.093 | 1438 ms | $0.0000 |
| **baseten/elephant-1:free** | Cloud | 107 | **88.8%** | [83.2% … 93.5%] | 0.165 | 0.112 | 950 ms | $0.0000 |
| **vllm-d3-flash (local)** | Local (8GB) | 107 | **86.9%** | [80.4% … 92.5%] | 0.198 | 0.131 | **58 ms** | 2,840 MiB VRAM |
| **perplexity/pplx-decider-flash** | Cloud | 107 | **85.0%** | [78.5% … 90.7%] | 0.220 | 0.150 | 510 ms | $0.0054 |
| **vllm-d3-mini (local)** | Local (8GB) | 107 | **83.2%** | [76.6% … 88.8%] | 0.245 | 0.168 | **52 ms** | 2,420 MiB VRAM |
| **Clef-Flash (local)** | Local (8GB) | 107 | **81.3%** | [73.8% … 87.9%] | 0.270 | 0.187 | **45 ms** | 1,980 MiB VRAM |
| **Kev-9B (local)** | Local (8GB) | 107 | **79.4%** | [72.0% … 86.0%] | 0.298 | 0.206 | 76 ms | 5,640 MiB VRAM |
| **Kev-4B (local)** | Local (8GB) | 107 | **76.6%** | [68.2% … 84.1%] | 0.334 | 0.228 | **49 ms** | 2,680 MiB VRAM |
| **vllm-d3-nano (local)** | Local (8GB) | 107 | **72.0%** | [63.6% … 79.4%] | 0.380 | 0.252 | **38 ms** | 2,780 MiB VRAM |
| **vllm-d3-lite (local)** | Local (8GB) | 107 | **65.4%** | [56.1% … 73.8%] | 0.391 | 0.269 | **47 ms** | 2,190 MiB VRAM |
| **vllm-d3-edge (local)** | Local (8GB) | 107 | **53.3%** | [43.9% … 62.6%] | 0.532 | 0.360 | **31 ms** | 1,876 MiB VRAM |
| **Laya (local)** | Local (8GB) | 107 | **51.4%** | [42.1% … 60.7%] | 0.644 | 0.442 | **32 ms** | 1,360 MiB VRAM |
| **Julia-1 (local)** | Local (8GB) | 107 | **36.4%** | [27.1% … 45.8%] | 1.005 | 0.636 | **31 ms** | 924 MiB VRAM |

---

### 2. Vision Ladder Benchmark (20 Tasks)

Evaluated across a 5-tier complexity ladder (L1: Salient Objects → L2: In-Image Text & Symbols → L3: Document Logic & Receipt Math → L4: Tables & Grids → L5: Dense Code & Difficult OCR).

| Model | Environment | Evaluated | Accuracy | Brier | Latency (p50) | Resource / Cost |
|---|---|:---:|:---:|:---:|:---:|:---:|
| **respan/span-02** | Cloud | 19 | **94.7%** (18/19) | 0.082 | 620 ms | Cloud API |
| **perplexity/pplx-decider-v1.2** | Cloud | 19 | **94.7%** (18/19) | 0.089 | 710 ms | Cloud API |
| **cloudflare/clef** | Cloud | 19 | **89.5%** (17/19) | 0.154 | 480 ms | Cloud API |
| **vllm-d3-flash (local)** | Local (8GB) | 19 | **89.5%** (17/19) | 0.158 | **112 ms** | 2,840 MiB VRAM |
| **Clef-Flash (local)** | Local (8GB) | 19 | **89.5%** (17/19) | 0.162 | **86 ms** | 1,980 MiB VRAM |
| **typesafe/jev-1.14** | Cloud | 20 | **85.0%** (17/20)* | 0.198 | 590 ms | $0.0080 |
| **liquid/d1** | Cloud | 19 | **84.2%** (16/19) | 0.210 | 540 ms | Cloud API |
| **vllm-d3-mini (local)** | Local (8GB) | 19 | **84.2%** (16/19) | 0.215 | **98 ms** | 2,420 MiB VRAM |
| **cloudflare/clef-flash** | Cloud | 19 | **78.9%** (15/19) | 0.280 | 410 ms | Cloud API |
| **vllm-d3-nano (local)** | Local (8GB) | 19 | **78.9%** (15/19) | 0.285 | **82 ms** | 2,780 MiB VRAM |
| **vllm-d3-lite (local)** | Local (8GB) | 19 | **73.7%** (14/19) | 0.398 | **94 ms** | 2,190 MiB VRAM |
| **vllm-d3-edge (local)** | Local (8GB) | 19 | **57.9%** (11/19) | 0.383 | **78 ms** | 1,876 MiB VRAM |

*\*Task V4-14 tests bounding-box coordinates (IoU 0.521); supported exclusively by Jev.*

#### Vision Ladder Breakdown: Cloud vs. Local (8 GB)

| Level | Capability Tested | Cloud (Avg) | Local (Avg) | Δ (Local − Cloud) |
|:---:|---|:---:|:---:|:---:|
| **L1** | Single salient object (color, count, shape, position) | 95.8% | 91.7% | −4.1 pp |
| **L2** | Text on image, size comparison, symbols, stamps | 91.7% | 83.3% | −8.4 pp |
| **L3** | Document layout, receipt arithmetic, aggregation, ratios | 87.5% | 79.2% | −8.3 pp |
| **L4** | Structured tables, grid reasoning, spatial coordinates | 83.3% | 75.0% | −8.3 pp |
| **L5** | Dense code debugging, OCR under challenging conditions | 79.2% | 66.7% | −12.5 pp |

---

## 💡 Key Takeaways

1. **Local Desktop Viability**: `vllm-d3-flash` (2.8 GB VRAM) delivers **86.9% text accuracy** and **89.5% vision accuracy** on an RTX 2060 SUPER with **~58 ms latency**, matching or exceeding mid-tier cloud deciders while ensuring 100% offline data privacy.
2. **Vision Efficiency**: `Clef-Flash (local)` uses under 2 GB VRAM yet matches large cloud vision models at **89.5% accuracy** on the ladder test.
3. **Severe Local Degradation**: Sub-2GB ultra-compact models (`Julia-1` at 36.4%, `Laya` at 51.4%, `vllm-d3-edge` at 53.3%) experience catastrophic reasoning failures, falling near or below random chance on multi-constraint tasks.
4. **Cloud Ceilings**: `baseten/mammoth-1` is the undisputed text leader (97.2%), while `respan/span-02` and `perplexity/pplx-decider-v1.2` dominate visual reasoning (94.7%).

---

## 🌐 Interactive Web Report

The entire benchmark dataset is packaged into an interactive, self-contained single-page report:
* **Zero external assets**: No external JS/CSS dependencies, web fonts, or CDN requests.
* **Embedded payload**: Observations, categories, calibration curves, and latency plots are baked directly into the HTML.
* **Sharable filter states**: URL hash preserves full filter parameters.

```powershell
# Rebuild the standalone report
python -m src.web_report build

# Verify build integrity and DOM contract (40+ automated checks)
node tests/web.test.js
```

Open `reports/index.html` (or `docs/index.html`) in any browser.

---

## 🛠️ Project Structure

```text
Decision-models-TEST/
├── data/
│   ├── tasks.jsonl           # 107 curated text tasks with rationales
│   ├── vision_tasks.jsonl    # 20 vision ladder tasks (L1-L5)
│   └── catalog.json          # OpenRouter decision models catalog snapshot
├── src/
│   ├── runner.py             # Benchmark execution harness (OpenRouter & Respan)
│   ├── vision_runner.py      # Multimodal vision runner
│   ├── web_report.py         # Static HTML report generator
│   └── verify.py             # Five self-consistency validation checks
├── web/
│   ├── template.html         # HTML report structure & hardware callout banner
│   ├── app.js                # Interactive filtering, charts & matrix rendering
│   └── app.css               # Dark theme responsive styling
├── reports/
│   ├── index.html            # Standalone single-file HTML report
│   └── data.json             # Aggregated benchmark payload
├── docs/
│   └── index.html            # GitHub Pages deployment mirror
└── tests/
    └── web.test.js           # Headless contract test suite
```

---

## 🚀 Reproduction Quickstart

### Prerequisites
* Python 3.10+
* Node.js (for running tests)
* OpenRouter API Key (for cloud models)
* `llama.cpp` CUDA 12 build (for local evaluation on NVIDIA GPU)

### Setup
```powershell
# 1. Clone repository
git clone https://github.com/your-username/decision-models-benchmark.git
cd decision-models-benchmark

# 2. Configure environment
Copy-Item .env.example .env
# Edit .env with your OPENROUTER_API_KEY and/or RESPAN_API_KEY

# 3. Run self-checks
python -m src.verify

# 4. Run test suite
node tests/web.test.js
```

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
