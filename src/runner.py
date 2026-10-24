"""Benchmark runner: probe, run, score.

    python -m src.runner probe
    python -m src.runner run --limit 3 --repeats 1
    python -m src.runner run
    python -m src.runner score --run runs/<id>
    python -m src.runner report --run runs/<id>

The raw store is append-only JSONL, so an interrupted run resumes exactly where
it stopped and never pays twice for the same (model, task, repeat).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import metrics  # noqa: E402
from src.client import ApiError, Client  # noqa: E402
from src.normalizer import NormalizationError, normalize  # noqa: E402
from src.tasks import load  # noqa: E402

RUNS = ROOT / "runs"
CACHE = ROOT / "cache"


def load_models(path: Path | None = None) -> list[dict]:
    path = path or ROOT / "config" / "models.json"
    cfg = json.loads(path.read_text(encoding="utf-8"))
    return cfg["models"], cfg.get("span_only")


def build_payload(model: str, task: dict) -> dict:
    return {
        "model": model,
        "state": task["state"],
        "questions": task["questions"],
        "session_id": f"bench-{task['id']}",
    }


def new_run(prefix: str = "run") -> Path:
    run_id = time.strftime(f"{prefix}-%Y%m%d-%H%M%S")
    path = RUNS / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_raw(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def append_raw(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------- probe
def cmd_probe(args) -> int:
    models, span = load_models()
    tasks = load()
    task = next(t for t in tasks if t["id"] == "CH-001")
    client = Client(min_interval=0.2, cache_dir=None)
    out = []
    for cfg in models:
        slug = cfg["slug"]
        started = time.monotonic()
        try:
            resp, meta = client.call(build_payload(slug, task), use_cache=False)
            answers = normalize(resp)
            row = {
                "model": slug,
                "ok": True,
                "latency_ms": meta["latency_ms"],
                "cost": resp.get("usage", {}).get("cost"),
                "input_tokens": resp.get("usage", {}).get("input_tokens"),
                "output_tokens": resp.get("usage", {}).get("output_tokens"),
                "resolved_model": resp.get("model"),
                "provider": resp.get("provider"),
                "answers": answers,
                "wall_ms": round((time.monotonic() - started) * 1000),
            }
        except (ApiError, NormalizationError) as exc:
            row = {"model": slug, "ok": False, "error": str(exc)[:400]}
        out.append(row)
        status = "ok" if row["ok"] else f"FAIL {row.get('error', '')[:120]}"
        print(f"{slug:<42} {status}")
    run = new_run("probe")
    (run / "probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwritten: {run / 'probe.json'}")
    return 0 if all(r["ok"] for r in out) else 1


# ----------------------------------------------------------------------- run
def cmd_run(args) -> int:
    models, _span = load_models()
    tasks = load()
    if args.tasks:
        wanted = {t.strip() for t in args.tasks.split(",")}
        tasks = [t for t in tasks if t["id"] in wanted]
    if args.limit:
        tasks = tasks[: args.limit]
    if args.models:
        wanted = {m.strip() for m in args.models.split(",")}
        models = [m for m in models if m["slug"] in wanted]

    run = Path(args.run) if args.run else new_run()
    run.mkdir(parents=True, exist_ok=True)
    raw_path = run / "raw.jsonl"
    done = {(r["model"], r["task_id"], r.get("repeat", 0))
            for r in read_raw(raw_path) if r.get("ok")}
    if args.force:
        done.clear()

    client = Client(min_interval=args.min_interval, cache_dir=None if args.no_cache else CACHE / "http")
    manifest = {
        "run": run.name,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "models": [m["slug"] for m in models],
        "tasks": len(tasks),
        "repeats": args.repeats,
        "no_cache": args.no_cache,
    }
    (run / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(tasks) * len(models) * args.repeats
    done_count = 0
    failures = 0
    started = time.monotonic()

    for model_cfg in models:
        slug = model_cfg["slug"]
        for task in tasks:
            for repeat in range(args.repeats):
                done_count += 1
                if (slug, task["id"], repeat) in done:
                    continue
                row = {
                    "task_id": task["id"],
                    "family": task["family"],
                    "lang": task["lang"],
                    "model": slug,
                    "repeat": repeat,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                try:
                    resp, meta = client.call(build_payload(slug, task))
                    answers = normalize(resp)
                    expected = list(task["questions"])
                    missing = [q for q in expected if q not in answers]
                    if missing:
                        raise NormalizationError(f"missing answers for {missing}")
                    row.update(
                        ok=True,
                        answers=answers,
                        usage=resp.get("usage", {}),
                        resolved_model=resp.get("model"),
                        provider=resp.get("provider"),
                        latency_ms=meta["latency_ms"],
                        attempts=meta["attempts"],
                        cached=meta["cached"],
                        gen_id=resp.get("id"),
                    )
                except (ApiError, NormalizationError) as exc:
                    failures += 1
                    row.update(ok=False, error=str(exc)[:600])
                append_raw(raw_path, row)
                if done_count % 20 == 0 or done_count == total:
                    elapsed = time.monotonic() - started
                    print(
                        f"[{done_count}/{total}] model={slug} task={task['id']} "
                        f"ok={row.get('ok')} {row.get('latency_ms', '-')}ms "
                        f"elapsed={elapsed:.0f}s fails={failures}"
                    )

    print(f"\nrun: {run}")
    print(f"raw: {raw_path}  rows={len(read_raw(raw_path))}  failures={failures}  "
          f"http_calls={client.calls} cache_hits={client.cache_hits} retries={client.retries}")
    return 0


# --------------------------------------------------------------------- score
def _question_score(qtype: str, gold, answer: dict) -> dict:
    """Score one answer against one gold label."""
    if qtype == "choice":
        probs = answer["probs"]
        value = answer["value"]
        p_true = float(probs.get(gold, 0.0))
        return {
            "correct": int(value == gold),
            "p_true": p_true,
            "brier": metrics.multiclass_brier(probs, gold),
            "confidence": float(answer.get("confidence") or max(probs.values())),
            "predicted": value,
            "gold": gold,
        }
    if qtype == "noul":
        p = float(answer["value"])
        pred = p >= 0.5
        return {
            "correct": int(pred == gold),
            "p_true": metrics.p_true_binary(p, gold),
            "brier": metrics.binary_brier(p, gold),
            "confidence": max(p, 1.0 - p),
            "predicted": pred,
            "gold": gold,
        }
    # score
    value = float(answer["value"])
    probs = answer.get("probs") or {}
    p_true = float(probs.get(gold, 0.0))
    return {
        "correct": int(round(value) == gold),
        "p_true": p_true,
        "brier": metrics.multiclass_brier({int(k): v for k, v in probs.items()}, gold),
        "confidence": float(answer.get("confidence") or 0.0),
        "predicted": value,
        "gold": gold,
        "abs_error": abs(value - gold),
    }


def build_summary(run: Path) -> dict:
    # A retried row appends a second line for the same key; the last one wins.
    latest: dict[tuple, dict] = {}
    for row in read_raw(run / "raw.jsonl"):
        latest[(row["model"], row["task_id"], row.get("repeat", 0))] = row
    rows = list(latest.values())
    tasks = {t["id"]: t for t in load()}
    per_model: dict[str, list[dict]] = {}
    for row in rows:
        if not row.get("ok"):
            per_model.setdefault(row["model"], []).append({"failed": row})
            continue
        task = tasks[row["task_id"]]
        items = []
        for qid, spec in task["questions"].items():
            try:
                items.append(
                    _question_score(spec["type"], task["gold"][qid], row["answers"][qid])
                    | {"task_id": row["task_id"], "family": task["family"],
                       "qid": qid, "qtype": spec["type"], "lang": task["lang"],
                       "levels": len(spec["criteria"]) if spec["type"] == "score" else None}
                )
            except (KeyError, TypeError, ValueError):
                items.append({"failed": {"error": "unscorable", "task_id": row["task_id"]}})
        per_model.setdefault(row["model"], []).extend(items)

    # No timestamp here on purpose: build_summary must be a pure function of the
    # raw store, otherwise two scorings of the same run produce different files
    # and the reproducibility check can never pass.
    summary = {"run": run.name, "models": {}}

    for model, items in sorted(per_model.items()):
        good = [i for i in items if "failed" not in i]
        failed = [i for i in items if "failed" in i]
        if not good:
            summary["models"][model] = {"failed": len(failed)}
            continue
        corrects = [i["correct"] for i in good]
        confs = [i["confidence"] for i in good]
        p_trues = [i["p_true"] for i in good]

        by_family: dict[str, dict] = {}
        for i in good:
            fam = by_family.setdefault(i["family"], {"n": 0, "correct": 0})
            fam["n"] += 1
            fam["correct"] += i["correct"]

        entry = {
            "n": len(good),
            "failed": len(failed),
            "accuracy": metrics.accuracy(corrects),
            "accuracy_ci": metrics.wilson_ci(sum(corrects), len(corrects)),
            "brier": sum(i["brier"] for i in good) / len(good),
            "nll": sum(metrics.log_loss(p) for p in p_trues) / len(p_trues),
            "ece": metrics.ece(confs, corrects),
            "calibration": metrics.reliability_table(confs, corrects),
            "by_family": {
                f: {"n": v["n"], "accuracy": v["correct"] / v["n"]} for f, v in sorted(by_family.items())
            },
            "latency": metrics.summarize([r["latency_ms"] for r in rows
                                          if r["model"] == model and r.get("ok")]),
            "cost_usd": sum((r.get("usage") or {}).get("cost") or 0 for r in rows if r["model"] == model),
            "input_tokens": sum((r.get("usage") or {}).get("input_tokens") or 0 for r in rows if r["model"] == model),
            "output_tokens": sum((r.get("usage") or {}).get("output_tokens") or 0 for r in rows if r["model"] == model),
        }

        # score-family extras. A raw QWK is invalid here: each item carries its
        # own rubric length, so the pooled rating scale is not shared. We report
        # scale-free normalised MAE instead.
        score_items = [i for i in good if i["qtype"] == "score"]
        if score_items:
            entry["score_mae"] = sum(i["abs_error"] for i in score_items) / len(score_items)
            entry["score_nmae"] = sum(
                i["abs_error"] / max(1, (i["levels"] or 5) - 1) for i in score_items
            ) / len(score_items)
            # Systematic displacement from the gold level: positive means the
            # model grades higher than the rubric, negative means lower.
            entry["score_bias"] = sum(
                i["predicted"] - i["gold"] for i in score_items
            ) / len(score_items)
            hist: dict[str, int] = {}
            for i in score_items:
                key = str(int(round(i["predicted"])))
                hist[key] = hist.get(key, 0) + 1
            entry["score_pred_hist"] = dict(sorted(hist.items()))

        # abstention behaviour
        abst = [i for i in good if i["family"] == "abstention"]
        non_abst = [i for i in good if i["family"] != "abstention"]
        entry["abstention_rate_on_unanswerable"] = (
            sum(1 for i in abst if i["predicted"] == "insufficient_data") / len(abst) if abst else None
        )
        entry["false_abstention_rate"] = (
            sum(1 for i in non_abst if i["predicted"] == "insufficient_data") / len(non_abst)
            if non_abst else None
        )

        # ru/en parity on twins
        twins = {}
        for i in good:
            if i["family"] == "multilingual":
                twins.setdefault(i["task_id"].rsplit("-", 1)[0], {})[i["lang"]] = i
        parity = []
        for base, pair in twins.items():
            if "ru" in pair and "en" in pair:
                parity.append(int(pair["ru"]["predicted"] == pair["en"]["predicted"]))
        entry["language_parity"] = (sum(parity) / len(parity)) if parity else None
        entry["twin_pairs"] = len(parity)

        summary["models"][model] = entry

    # model-vs-model comparisons on paired per-task outcomes
    common = None
    outcomes: dict[str, dict[str, float]] = {}
    for model, entry in summary["models"].items():
        if "by_family" not in entry:
            continue
        outcomes[model] = {}
        for i in [x for x in per_model[model] if "failed" not in x]:
            outcomes[model][f"{i['task_id']}:{i['qid']}"] = float(i["correct"])
        common = set(outcomes[model]) if common is None else common & set(outcomes[model])
    comparisons = {}
    names = sorted(outcomes)
    if common:
        for a in range(len(names)):
            for b in range(a + 1, len(names)):
                ma, mb = names[a], names[b]
                va = [outcomes[ma][k] for k in sorted(common)]
                vb = [outcomes[mb][k] for k in sorted(common)]
                comparisons[f"{ma} vs {mb}"] = metrics.paired_bootstrap(va, vb, n_boot=2000)
    summary["comparisons"] = comparisons
    summary["paired_tasks"] = len(common) if common else 0
    return summary


def cmd_score(args) -> int:
    run = Path(args.run)
    summary = build_summary(run)
    (run / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    for model, entry in summary["models"].items():
        if "accuracy" not in entry:
            print(f"{model:<42} no scorable answers")
            continue
        lo, hi = entry["accuracy_ci"]
        print(
            f"{model:<42} n={entry['n']:<4} acc={entry['accuracy']:.3f} "
            f"[{lo:.2f},{hi:.2f}] brier={entry['brier']:.3f} "
            f"ece={entry['ece']:.3f} p50={entry['latency']['p50']:.0f}ms "
            f"${entry['cost_usd']:.4f}"
        )
    print(f"\nsummary: {run / 'summary.json'}")
    return 0


def cmd_report(args) -> int:
    from src.report import write_markdown, write_xlsx

    run = Path(args.run)
    summary_path = run / "summary.json"
    if not summary_path.exists():
        cmd_score(args)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    md = write_markdown(summary, run)
    xlsx = write_xlsx(summary, run)
    print(f"markdown: {md}")
    print(f"xlsx: {xlsx}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Decision model benchmark")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("probe", help="one call per model, write probe.json")
    p.set_defaults(func=cmd_probe)

    p = sub.add_parser("run", help="run the benchmark")
    p.add_argument("--run", help="existing run directory to resume")
    p.add_argument("--models", help="comma separated slugs")
    p.add_argument("--tasks", help="comma separated task ids")
    p.add_argument("--limit", type=int, help="only the first N tasks")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--min-interval", type=float, default=0.2, dest="min_interval")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--force", action="store_true", help="ignore resume state and re-send")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("score", help="score a run into summary.json")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("report", help="render markdown and xlsx")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
