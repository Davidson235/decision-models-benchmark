"""Run the 20 vision tasks against a local llama-server with a vision projector.

    python -m src.local_vision --endpoint http://127.0.0.1:9940/v1/systemone --model d3-mini

Same tasks, same scoring as the cloud vision run. Box questions are stripped:
only Jev implements that primitive, and sending it to another model returns 400
before the image is read.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.vision import TASKS_V, render_png  # noqa: E402
from src import metrics  # noqa: E402
from src.client import ApiError, Client  # noqa: E402
from src.normalizer import NormalizationError, normalize  # noqa: E402
from src.runner import _question_score  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", default="http://127.0.0.1:9940/v1/systemone")
    ap.add_argument("--model", default="local")
    ap.add_argument("--out", default="runs/local-vision.json")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--warmup", type=int, default=0,
                    help="dummy image requests before measuring (first one compiles/loads the projector)")
    args = ap.parse_args(argv)

    os.environ.setdefault("OPENROUTER_API_KEY", "local")
    assets = ROOT / "runs" / "local-assets"

    tasks = TASKS_V[: args.limit] if args.limit else TASKS_V
    client = Client(endpoint=args.endpoint, timeout=180, min_interval=0.0, cache_dir=None)

    if args.warmup:
        warm_task = TASKS_V[0]
        png = render_png(warm_task, assets)
        b64 = base64.b64encode(png.read_bytes()).decode()
        warm = {"model": args.model,
                "state": "Прогрев.",
                "images": [f"data:image/png;base64,{b64}"],
                "questions": {"q": {"type": "noul", "instructions": "Есть объект?",
                                    "criteria": {"true": "да", "false": "нет"}}}}
        for _ in range(args.warmup):
            try:
                client.call(warm, use_cache=False)
            except ApiError:
                break

    rows = []
    t0 = time.monotonic()
    for task in tasks:
        if task.get("box_only"):
            rows.append({"task_id": task["id"], "level": task["level"], "skipped": True})
            continue
        png = render_png(task, assets)
        b64 = base64.b64encode(png.read_bytes()).decode()
        qid = next(iter(task["questions"]))
        # llama.cpp's systemone takes media in a top-level `images` array of
        # plain data-URL strings. The OpenAI-style {"type":"image_url",...} part
        # inside `state` is silently tokenised as base64 text instead: the same
        # image then costs ~2200 tokens and the model answers at chance.
        payload = {
            "model": args.model,
            "state": "Изображение интерфейса или документа. Ответь на вопрос по картинке.",
            "images": [f"data:image/png;base64,{b64}"],
            "questions": {qid: task["questions"][qid]},
        }
        try:
            resp, meta = client.call(payload, use_cache=False)
            answers = normalize(resp)
            scored = _question_score(task["questions"][qid]["type"],
                                     task["gold"][qid], answers[qid])
            rows.append({"task_id": task["id"], "level": task["level"],
                         "family": task["family"], "ok": scored["correct"],
                         "conf": scored["confidence"], "brier": scored["brier"],
                         "latency_ms": meta["latency_ms"]})
        except (ApiError, NormalizationError) as exc:
            rows.append({"task_id": task["id"], "level": task["level"],
                         "error": str(exc)[:200]})

    good = [r for r in rows if "error" not in r and not r.get("skipped")]
    by_level: dict[str, dict] = {}
    for r in good:
        b = by_level.setdefault(str(r["level"]), {"n": 0, "ok": 0})
        b["n"] += 1
        b["ok"] += r["ok"]

    summary = {
        "model": args.model, "endpoint": args.endpoint,
        "n": len(good), "errors": sum(1 for r in rows if "error" in r),
        "skipped": sum(1 for r in rows if r.get("skipped")),
        "accuracy": metrics.accuracy([r["ok"] for r in good]) if good else None,
        "accuracy_ci": metrics.wilson_ci(sum(r["ok"] for r in good), len(good)) if good else None,
        "brier": sum(r["brier"] for r in good) / len(good) if good else None,
        "latency": metrics.summarize([r["latency_ms"] for r in good]) if good else None,
        "by_level": {k: round(v["ok"] / v["n"], 3) for k, v in sorted(by_level.items())},
        "per_task": {r["task_id"]: r["ok"] for r in good},
        "error_samples": [r["error"] for r in rows if "error" in r][:5],
        "wall_seconds": round(time.monotonic() - t0, 1),
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    acc = summary["accuracy"]
    print(f"{args.model}: vision acc={acc:.3f} n={summary['n']} "
          f"errors={summary['errors']} p50={summary['latency']['p50']:.0f}ms "
          f"levels={summary['by_level']}" if acc is not None else f"{args.model}: no scorable answers")
    print(f"saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
