"""Run the 107-task text corpus through Laya Multilingual (local checkpoint).

    python -m src.laya_bench
    python -m src.laya_bench --limit 10 --out runs/laya-quick.json

The model is loaded from a local directory, so huggingface_hub is never called
(HF_HUB_OFFLINE=1 is set defensively).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import metrics  # noqa: E402
from src.normalizer import NormalizationError, normalize  # noqa: E402
from src.runner import _question_score  # noqa: E402
from src.tasks import load  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-path", default=".tools/laya-multilingual")
    ap.add_argument("--out", default="runs/local-laya-multilingual.json")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args(argv)

    import laya

    t0 = time.monotonic()
    agent = laya.load(args.model_path)
    load_s = time.monotonic() - t0
    print(f"loaded in {load_s:.1f}s")

    tasks = load()
    if args.limit:
        tasks = tasks[: args.limit]

    rows = []
    t0 = time.monotonic()
    for i, task in enumerate(tasks, 1):
        started = time.perf_counter()
        try:
            raw = agent.predict(task["state"], task["questions"])
            latency = (time.perf_counter() - started) * 1000
            answers = normalize(raw)
            for qid, spec in task["questions"].items():
                scored = _question_score(spec["type"], task["gold"][qid], answers[qid])
                rows.append({
                    "task_id": task["id"], "family": task["family"],
                    "qtype": spec["type"], "lang": task["lang"],
                    "ok": scored["correct"], "p_true": scored["p_true"],
                    "brier": scored["brier"], "conf": scored["confidence"],
                    "latency_ms": round(latency, 1),
                })
        except (NormalizationError, KeyError, ValueError) as exc:
            rows.append({"task_id": task["id"], "family": task["family"],
                         "error": f"{type(exc).__name__}: {exc}"[:200]})
        if i % 25 == 0:
            print(f"  {i}/{len(tasks)}  {time.monotonic() - t0:.0f}s")

    good = [r for r in rows if "error" not in r]
    by_family: dict[str, dict] = {}
    for r in good:
        f = by_family.setdefault(r["family"], {"n": 0, "ok": 0})
        f["n"] += 1
        f["ok"] += r["ok"]

    correct = [r["ok"] for r in good]
    summary = {
        "model": "laya-multilingual",
        "checkpoint": args.model_path,
        "n": len(good),
        "errors": len(rows) - len(good),
        "accuracy": metrics.accuracy(correct) if good else None,
        "accuracy_ci": metrics.wilson_ci(sum(correct), len(correct)) if good else None,
        "brier": sum(r["brier"] for r in good) / len(good) if good else None,
        "ece": metrics.ece([r["conf"] for r in good], correct) if good else None,
        "latency": metrics.summarize([r["latency_ms"] for r in good]) if good else None,
        "by_family": {k: round(v["ok"] / v["n"], 3) for k, v in sorted(by_family.items())},
        "load_seconds": round(load_s, 1),
        "wall_seconds": round(time.monotonic() - t0, 1),
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if summary["accuracy"] is not None:
        print(f"\nlayа-multilingual: acc={summary['accuracy']:.3f} "
              f"CI={summary['accuracy_ci'][0]:.2f}-{summary['accuracy_ci'][1]:.2f} "
              f"brier={summary['brier']:.3f} ece={summary['ece']:.3f} "
              f"p50={summary['latency']['p50']:.0f}ms errors={summary['errors']}")
        print("by family:", summary["by_family"])
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
