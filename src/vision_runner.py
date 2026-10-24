"""Run the 20-task vision ladder against the decision models that accept images.

    python -m src.vision_runner
    python -m src.vision_runner --models typesafe/jev-1.14 --limit 5

Reuses the text benchmark's transport, normalizer and metrics. Box questions
are a Jev-only primitive and are stripped for every other model instead of
letting the whole request fail with a 400.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.vision import LEVEL_TITLES, TASKS_V, render_png  # noqa: E402
from src import metrics  # noqa: E402
from src.client import ApiError, Client  # noqa: E402
from src.normalizer import NormalizationError, normalize  # noqa: E402
from src.runner import _question_score, append_raw, read_raw  # noqa: E402

RUNS = ROOT / "runs"
CACHE = ROOT / "cache" / "vision"

MODELS = [
    "inception/mercury-decide:free",
    "perplexity/pplx-decider-flash-v1.2",
    "respan/span-02",
    "liquid/d1",
    "cloudflare/clef-flash",
    "typesafe/jev-1.14",
]

BOX_MODELS = {"typesafe/jev-1.13", "typesafe/jev-1.14", "~typesafe/jev-latest"}


def image_part(path: Path) -> dict:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}


def build_payload(model: str, task: dict, assets: Path) -> dict:
    png = render_png(task, assets)
    questions = dict(task["questions"])
    if task.get("box_only") and model not in BOX_MODELS:
        questions.pop("q", None)
        questions = {}
    state = [
        "Изображение интерфейса или документа. Ответь на вопрос по картинке.",
        image_part(png),
    ]
    return {"model": model, "state": state, "questions": questions,
            "session_id": f"vision-{task['id']}"}


def iou(pred: dict, gold: dict) -> float:
    try:
        pl, pr = float(pred["left"]), float(pred["right"])
        pt, pb = float(pred["top"]), float(pred["bottom"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    inter_w = max(0.0, min(pr, gold["right"]) - max(pl, gold["left"]))
    inter_h = max(0.0, min(pb, gold["bottom"]) - max(pt, gold["top"]))
    inter = inter_w * inter_h
    union = ((pr - pl) * (pb - pt) + (gold["right"] - gold["left"]) *
             (gold["bottom"] - gold["top"]) - inter)
    return inter / union if union > 0 else 0.0


def cmd_run(args) -> int:
    tasks = TASKS_V[: args.limit] if args.limit else TASKS_V
    models = [m.strip() for m in args.models.split(",")] if args.models else MODELS
    run = Path(args.run) if args.run else RUNS / time.strftime("vision-%Y%m%d-%H%M%S")
    run.mkdir(parents=True, exist_ok=True)
    assets = run / "assets"
    raw_path = run / "raw.jsonl"
    done = {(r["model"], r["task_id"]) for r in read_raw(raw_path) if r.get("ok")}

    client = Client(min_interval=0.3, cache_dir=None if args.no_cache else CACHE)
    total = len(tasks) * len(models)
    n = 0
    for model in models:
        for task in tasks:
            n += 1
            if (model, task["id"]) in done:
                continue
            row = {"model": model, "task_id": task["id"], "level": task["level"],
                   "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            payload = build_payload(model, task, assets)
            if not payload["questions"]:
                row.update(ok=None, skipped="box question not supported by this model")
                append_raw(raw_path, row)
                print(f"[{n}/{total}] {model} {task['id']} SKIP (box-only)")
                continue
            try:
                resp, meta = client.call(payload)
                answers = normalize(resp)
                missing = [q for q in payload["questions"] if q not in answers]
                if missing:
                    raise NormalizationError(f"missing answers: {missing}")
                row.update(ok=True, answers=answers, usage=resp.get("usage", {}),
                           latency_ms=meta["latency_ms"], provider=resp.get("provider"),
                           resolved_model=resp.get("model"))
            except (ApiError, NormalizationError) as exc:
                row.update(ok=False, error=str(exc)[:500])
            append_raw(raw_path, row)
            print(f"[{n}/{total}] {model} {task['id']} ok={row.get('ok')} "
                  f"{row.get('latency_ms', '-')}ms")

    print(f"\nrun: {run}")
    return 0


def score(run: Path) -> dict:
    latest: dict = {}
    for row in read_raw(run / "raw.jsonl"):
        latest[(row["model"], row["task_id"])] = row
    rows = [r for r in latest.values() if r.get("ok")]
    per_model: dict[str, list[dict]] = {}
    for row in rows:
        task = next(t for t in TASKS_V if t["id"] == row["task_id"])
        qid = next(iter(task["gold"]))
        gold = task["gold"][qid]
        ans = row["answers"][qid]
        if task.get("box_only"):
            value = iou(ans["value"], gold)
            item = {"correct": int(value >= 0.5), "iou": value, "level": task["level"],
                    "task_id": task["id"]}
        else:
            scored = _question_score(task["questions"][qid]["type"], gold, ans)
            item = {"correct": scored["correct"], "level": task["level"],
                    "task_id": task["id"], "confidence": scored["confidence"],
                    "brier": scored["brier"], "p_true": scored["p_true"]}
        per_model.setdefault(row["model"], []).append(item)

    summary = {"run": run.name, "models": {}}
    for model, items in sorted(per_model.items()):
        correct = [i["correct"] for i in items]
        by_level: dict[str, dict] = {}
        for i in items:
            b = by_level.setdefault(str(i["level"]), {"n": 0, "correct": 0})
            b["n"] += 1
            b["correct"] += i["correct"]
        entry = {
            "n": len(items),
            "accuracy": metrics.accuracy(correct),
            "accuracy_ci": metrics.wilson_ci(sum(correct), len(correct)),
            "by_level": {k: round(v["correct"] / v["n"], 3) for k, v in sorted(by_level.items())},
            "per_task": {i["task_id"]: i["correct"] for i in items},
        }
        # Mean confidence per level: accuracy can saturate while confidence keeps
        # falling, which is the signal that the ladder is actually biting.
        conf_levels: dict[str, list[float]] = {}
        for i in items:
            if "confidence" in i and i["confidence"] is not None:
                conf_levels.setdefault(str(i["level"]), []).append(float(i["confidence"]))
        if conf_levels:
            entry["confidence_by_level"] = {
                k: round(sum(v) / len(v), 3) for k, v in sorted(conf_levels.items())
            }
        boxes = [i["iou"] for i in items if "iou" in i]
        if boxes:
            entry["box_iou"] = round(sum(boxes) / len(boxes), 3)
        if all("brier" in i for i in items):
            entry["brier"] = round(sum(i["brier"] for i in items) / len(items), 3)
        summary["models"][model] = entry
    return summary


def report(summary: dict, run: Path) -> Path:
    ranked = sorted(summary["models"].items(), key=lambda kv: kv[1]["accuracy"], reverse=True)
    lines = [f"# Vision Ladder — {summary['run']}", "",
             f"20 задач, 5 уровней по 4. Модели: {len(ranked)}.", "",
             "## Точность по уровням", "",
             "| Модель | все | " + " | ".join(LEVEL_TITLES[i] for i in range(1, 6)) + " |",
             "|---|---|" + "---|" * 5]
    for model, e in ranked:
        lv = e["by_level"]
        lines.append(f"| `{model}` | **{e['accuracy']:.3f}** | " +
                     " | ".join(f"{lv.get(str(i), 0):.2f}" for i in range(1, 6)) + " |")
    lines += ["", "## Провалы по задачам", "",
              "| Модель | " + " | ".join(t["id"] for t in TASKS_V) + " |",
              "|---|" + "---|" * len(TASKS_V)]
    for model, e in ranked:
        cells = ["—" if t["id"] not in e["per_task"]
                 else ("✓" if e["per_task"][t["id"]] else "✗") for t in TASKS_V]
        lines.append(f"| `{model}` | " + " | ".join(cells) + " |")
    lines.append("")
    lines += ["", "## Средняя уверенность по уровням", "",
              "| Модель | " + " | ".join(LEVEL_TITLES[i] for i in range(1, 6)) + " |",
              "|---|" + "---|" * 5]
    for model, e in ranked:
        cb = e.get("confidence_by_level") or {}
        lines.append(f"| `{model}` | " +
                     " | ".join(f"{cb.get(str(i), float('nan')):.2f}" for i in range(1, 6)) + " |")
    lines.append("")
    # Empirical difficulty: how many of the models solved each task. The
    # designed level is an a-priori guess; this table is the measurement.
    solved: dict[str, int] = {}
    attempted: dict[str, int] = {}
    for _, e in ranked:
        for tid, ok in e["per_task"].items():
            attempted[tid] = attempted.get(tid, 0) + 1
            solved[tid] = solved.get(tid, 0) + int(bool(ok))
    order = sorted(TASKS_V, key=lambda t: (solved.get(t["id"], 0) / max(1, attempted.get(t["id"], 1)),
                                           t["level"]))
    lines += ["## Эмпирическая сложность", "",
              "| Задача | Проектный уровень | Решили |", "|---|---|---|"]
    for t in order:
        lines.append(f"| {t['id']} | L{t['level']} | "
                     f"{solved.get(t['id'], 0)}/{attempted.get(t['id'], 0)} |")
    lines += ["", "Проектный уровень — априорная догадка, порядок строк — измерение. "
              "Там, где они расходятся, верить надо второму столбцу.", ""]

    boxes = [(m, e["box_iou"]) for m, e in ranked if "box_iou" in e]
    if boxes:
        lines += ["## Box (IoU, V5-18)", ""]
        for model, v in boxes:
            lines.append(f"- `{model}`: IoU {v:.3f} (порог 0.5)")
    path = run / "report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def cmd_score(args) -> int:
    run = Path(args.run)
    summary = score(run)
    (run / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    for model, e in sorted(summary["models"].items(), key=lambda kv: -kv[1]["accuracy"]):
        print(f"{model:<40} acc={e['accuracy']:.3f} n={e['n']:<3} "
              f"levels={e['by_level']}")
    print(f"\nsummary: {run / 'summary.json'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--run")
    p.add_argument("--models")
    p.add_argument("--limit", type=int)
    p.add_argument("--no-cache", action="store_true")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("score")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_score)
    args = ap.parse_args(argv)
    rc = args.func(args)
    if args.cmd == "score":
        run = Path(args.run)
        summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
        print(f"report: {report(summary, run)}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
