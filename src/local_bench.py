"""Run the text corpus against a local llama-server implementing /v1/systemone.

    python -m src.local_bench --endpoint http://127.0.0.1:9931/v1/systemone --model kev

Reuses the same tasks, the same normalizer and the same scoring as the cloud
benchmark, so the numbers are directly comparable.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import metrics  # noqa: E402
from src.client import ApiError, Client  # noqa: E402
from src.normalizer import NormalizationError, normalize  # noqa: E402
from src.runner import _question_score  # noqa: E402
from src.tasks import load  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://127.0.0.1:9931/v1/systemone")
    ap.add_argument("--model", default="kev")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--warmup", type=int, default=0,
                    help="dummy requests before measuring, to leave the cold-start regime")
    ap.add_argument("--out", default="runs/local-kev.json")
    args = ap.parse_args(argv)

    # llama-server ignores the header, but the client refuses to build a request
    # without it, so a dummy value keeps one code path for both runs.
    os.environ.setdefault("OPENROUTER_API_KEY", "local")

    tasks = load()
    if args.limit:
        tasks = tasks[: args.limit]

    client = Client(endpoint=args.endpoint, timeout=120, min_interval=0.0, cache_dir=None)

    if args.warmup:
        warm = {"model": args.model,
                "state": {"ticket": "Прогрев: оплата не прошла."},
                "questions": {"q": {"type": "noul", "instructions": "Клиент просит возврат?",
                                    "criteria": {"true": "да", "false": "нет"}}}}
        for _ in range(args.warmup):
            try:
                client.call(warm, use_cache=False)
            except ApiError:
                break
    rows = []
    t0 = time.monotonic()
    for i, task in enumerate(tasks, 1):
        payload = {"model": args.model, "state": task["state"],
                   "questions": task["questions"]}
        try:
            resp, meta = client.call(payload, use_cache=False)
            answers = normalize(resp)
            for qid, spec in task["questions"].items():
                scored = _question_score(spec["type"], task["gold"][qid], answers[qid])
                rows.append({
                    "task_id": task["id"], "family": task["family"], "qtype": spec["type"],
                    "lang": task["lang"], "ok": scored["correct"],
                    "p_true": scored["p_true"], "brier": scored["brier"],
                    "conf": scored["confidence"], "latency_ms": meta["latency_ms"],
                })
        except (ApiError, NormalizationError) as exc:
            rows.append({"task_id": task["id"], "family": task["family"], "error": str(exc)[:200]})
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
        "model": args.model,
        "endpoint": args.endpoint,
        "n": len(good),
        "errors": len(rows) - len(good),
        "accuracy": metrics.accuracy(correct) if good else None,
        "accuracy_ci": metrics.wilson_ci(sum(correct), len(correct)) if good else None,
        "brier": sum(r["brier"] for r in good) / len(good) if good else None,
        "ece": metrics.ece([r["conf"] for r in good], correct) if good else None,
        "latency": metrics.summarize([r["latency_ms"] for r in good]) if good else None,
        "by_family": {k: round(v["ok"] / v["n"], 3) for k, v in sorted(by_family.items())},
        "wall_seconds": round(time.monotonic() - t0, 1),
    }
    out = ROOT / args.out
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{args.model}: acc={summary['accuracy']:.3f} "
          f"CI={summary['accuracy_ci'][0]:.2f}-{summary['accuracy_ci'][1]:.2f} "
          f"brier={summary['brier']:.3f} ece={summary['ece']:.3f} "
          f"p50={summary['latency']['p50']:.0f}ms errors={summary['errors']}")
    print("by family:", summary["by_family"])
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
