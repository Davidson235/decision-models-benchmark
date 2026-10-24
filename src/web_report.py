"""Build the single-file web report from recorded runs.

    python -m src.web_report catalog      # refresh data/catalog.json (network)
    python -m src.web_report build        # reports/index.html + reports/data.json
    python -m src.web_report check        # invariants: observations vs summary.json

The build itself never touches the network and is deterministic for a fixed
input: two builds of the same runs produce byte-identical HTML.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.vision import TASKS_V  # noqa: E402
from src.runner import _question_score, read_raw  # noqa: E402
from src.tasks import load as load_text_tasks  # noqa: E402
from src.vision_runner import iou  # noqa: E402

RUNS = ROOT / "runs"
REPORTS = ROOT / "reports"
WEB = ROOT / "web"
CATALOG = ROOT / "data" / "catalog.json"

STATUSES = {"подтверждено", "опровергнуто", "частично", "непроверяемо", "несопоставимо"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def latest_run(prefix: str) -> Path:
    candidates = sorted(
        p for p in RUNS.glob(f"{prefix}-*")
        if p.is_dir() and (p / "summary.json").exists() and (p / "raw.jsonl").exists()
    )
    if not candidates:
        raise SystemExit(f"no finished run matching {prefix}-*")
    return candidates[-1]


# --------------------------------------------------------------------- sources
def text_observations(run: Path) -> list[dict]:
    tasks = {t["id"]: t for t in load_text_tasks()}
    latest: dict[tuple, dict] = {}
    for row in read_raw(run / "raw.jsonl"):
        latest[(row["model"], row["task_id"], row.get("repeat", 0))] = row

    obs = []
    for (model, task_id, _repeat), row in sorted(latest.items()):
        task = tasks[task_id]
        if not row.get("ok"):
            for qid in task["questions"]:
                obs.append(_obs("text", model, task_id, task["family"], 0,
                                task["lang"], task["difficulty"], None, None, None,
                                None, row.get("latency_ms"), 0.0, skipped=True))
            continue
        for qid, spec in task["questions"].items():
            answer = row["answers"][qid]
            scored = _question_score(spec["type"], task["gold"][qid], answer)
            obs.append(_obs(
                "text", model, task_id, task["family"], 0, task["lang"],
                task["difficulty"], scored["correct"], scored["p_true"],
                scored["brier"], scored["confidence"], row.get("latency_ms"),
                (row.get("usage") or {}).get("cost") or 0.0,
                pred=scored["predicted"], gold=task["gold"][qid],
            ))
    return obs


def vision_observations(run: Path) -> list[dict]:
    tasks = {t["id"]: t for t in TASKS_V}
    latest: dict[tuple, dict] = {}
    for row in read_raw(run / "raw.jsonl"):
        latest[(row["model"], row["task_id"])] = row

    obs = []
    for (model, task_id), row in sorted(latest.items()):
        task = tasks[task_id]
        qid = next(iter(task["gold"]))
        gold = task["gold"][qid]
        cost = (row.get("usage") or {}).get("cost") or 0.0
        if row.get("skipped") or row.get("ok") is None:
            obs.append(_obs("vision", model, task_id, task["family"], task["level"],
                            "ru", f"L{task['level']}", None, None, None, None,
                            None, 0.0, skipped=True))
            continue
        answer = row["answers"][qid]
        if task.get("box_only"):
            value = iou(answer["value"], gold)
            obs.append(_obs("vision", model, task_id, task["family"], task["level"],
                            "ru", f"L{task['level']}", int(value >= 0.5), None, None,
                            None, row.get("latency_ms"), cost,
                            pred=round(value, 3), gold="box"))
        else:
            scored = _question_score(task["questions"][qid]["type"], gold, answer)
            obs.append(_obs("vision", model, task_id, task["family"], task["level"],
                            "ru", f"L{task['level']}", scored["correct"],
                            scored["p_true"], scored["brier"], scored["confidence"],
                            row.get("latency_ms"), cost,
                            pred=scored["predicted"], gold=gold))
    return obs


def _obs(test, model, task, cat, level, lang, diff, ok, p, b, conf, lat, cost,
         skipped=False, pred=None, gold=None):
    def clean(x):
        if x is None:
            return None
        x = float(x)
        return None if (math.isnan(x) or math.isinf(x)) else round(x, 6)

    if isinstance(pred, (int, float)) and pred is not None:
        pred = clean(pred)

    return {
        "id": f"{test}|{model}|{task}",
        "test": test,
        "model": model,
        "task": task,
        "cat": cat,
        "level": level,
        "lang": lang,
        "diff": diff,
        "ok": None if skipped else int(ok),
        "p": clean(p),
        "b": clean(b),
        "conf": clean(conf),
        "lat": clean(lat),
        "cost": clean(cost),
        "skip": bool(skipped),
        "pred": pred,
        "gold": gold,
    }


def vision_cards(vision_run: Path) -> list[dict]:
    """Task metadata plus the rendered image, so the report can show the test."""
    assets = vision_run / "assets"
    cards = []
    for t in TASKS_V:
        qid = next(iter(t["questions"]))
        spec = t["questions"][qid]
        gold = t["gold"][qid]
        if spec["type"] == "choice":
            gold_label = spec["criteria"].get(gold, str(gold))
        elif spec["type"] == "noul":
            gold_label = "да" if gold else "нет"
        else:
            gold_label = "рамка вокруг объекта"
        png = assets / f"{t['id']}.png"
        b64 = base64.b64encode(png.read_bytes()).decode() if png.exists() else ""
        cards.append({
            "id": t["id"],
            "level": t["level"],
            "family": t["family"],
            "instructions": spec["instructions"],
            "type": spec["type"],
            "gold": gold,
            "gold_label": gold_label,
            "criteria": spec.get("criteria") if isinstance(spec.get("criteria"), dict) else None,
            "image": f"data:image/png;base64,{b64}" if b64 else "",
        })
    return cards


# --------------------------------------------------------------------- catalog
def refresh_catalog() -> int:
    import urllib.request
    import os

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    url = "https://openrouter.ai/api/v1/models?output_modalities=decisions"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())["data"]
    rows = [{
        "slug": m["id"],
        "name": m.get("name", ""),
        "modalities": m["architecture"]["input_modalities"],
        "price_in": float(m["pricing"]["prompt"]),
        "price_out": float(m["pricing"]["completion"]),
        "ctx": m.get("context_length", 0),
    } for m in data]
    rows.sort(key=lambda r: r["slug"])
    CATALOG.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"catalog: {len(rows)} models -> {CATALOG}")
    return len(rows)


def load_catalog() -> list[dict]:
    return json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []


# ------------------------------------------------------------------ assembly
def local_results() -> list[dict]:
    """Merge clean local runs with the measured VRAM/context configuration."""
    cfg_path = RUNS / "local-config.json"
    cfg = {c["model"]: c for c in json.loads(cfg_path.read_text(encoding="utf-8"))} if cfg_path.exists() else {}

    table: dict[str, dict] = {}
    for path in sorted(RUNS.glob("clean-*-text.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        name = row["model"]
        entry = table.setdefault(name, {"model": name})
        acc = row.get("accuracy")
        entry["text"] = round(acc, 3) if acc is not None else None
        lat = row.get("latency") or {}
        entry["text_p50"] = round(lat["p50"]) if "p50" in lat and lat["p50"] is not None else None
        entry["text_n"] = row.get("n", 0)
        entry["text_by_family"] = row.get("by_family", {})
        brier = row.get("brier")
        entry["text_brier"] = round(brier, 3) if brier is not None else None
        ece = row.get("ece")
        entry["text_ece"] = round(ece, 3) if ece is not None else None
        ci = row.get("accuracy_ci")
        entry["text_ci"] = [round(x, 3) for x in ci] if ci else None
        entry["text_errors"] = row.get("errors", 0)
    for path in sorted(RUNS.glob("clean-*-vision.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        name = row["model"]
        entry = table.setdefault(name, {"model": name})
        acc = row.get("accuracy")
        if acc is not None:
            entry["vision"] = round(acc, 3)
            lat = row.get("latency") or {}
            entry["vision_p50"] = round(lat["p50"]) if "p50" in lat and lat["p50"] is not None else None
            entry["vision_n"] = row.get("n", 0)
            entry["vision_by_level"] = row.get("by_level", {})
            entry["vision_per_task"] = row.get("per_task", {})
            brier = row.get("brier")
            entry["vision_brier"] = round(brier, 3) if brier is not None else None
            ci = row.get("accuracy_ci")
            entry["vision_ci"] = [round(x, 3) for x in ci] if ci else None
            entry["vision_skipped"] = row.get("skipped", 0)
            entry["vision_errors"] = row.get("errors", 0)

    out = []
    for name, entry in table.items():
        c = cfg.get(name, {})
        entry.update(ctx=c.get("ctx"), vram_mib=c.get("vram_mib"),
                     kv=c.get("kv", False), note=c.get("note", ""))
        out.append(entry)
    return sorted(out, key=lambda r: -(r.get("text") or 0))


def build_data() -> dict:
    text_run = latest_run("run")
    vision_run = latest_run("vision")
    obs = text_observations(text_run) + vision_observations(vision_run)

    models: dict[str, dict] = {}
    for o in obs:
        m = models.setdefault(o["model"], {"slug": o["model"], "test": o["test"],
                                           "tier": "free" if ":free" in o["model"] else "paid"})
    catalog = {row["slug"]: row for row in load_catalog()}
    for slug, m in models.items():
        row = catalog.get(slug, {})
        m["price_in"] = row.get("price_in", 0.0)
        m["modalities"] = row.get("modalities", ["text"])
        m["ctx"] = row.get("ctx", 0)

    claims = json.loads((REPORTS / "claims.json").read_text(encoding="utf-8"))
    problems = validate_claims(claims)
    if problems:
        raise SystemExit("claims.json invalid:\n  " + "\n  ".join(problems))

    # vision_runner's summary has no latency block; derive p50 from observations
    vision_summary = json.loads((vision_run / "summary.json").read_text(encoding="utf-8"))
    for model, entry in vision_summary.get("models", {}).items():
        lats = sorted(o["lat"] for o in obs
                      if o["test"] == "vision" and o["model"] == model and o["lat"])
        if lats:
            entry["latency"] = {"p50": round(lats[len(lats) // 2])}

    verify_path = RUNS / "verify.json"
    verify = json.loads(verify_path.read_text(encoding="utf-8")) if verify_path.exists() else []

    # Derived from the newest source file, not from the clock: the build must be
    # a pure function of its inputs, otherwise two builds differ byte for byte.
    newest = max((text_run / "raw.jsonl").stat().st_mtime,
                 (vision_run / "raw.jsonl").stat().st_mtime)
    data = {
        "meta": {
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(newest)),
            "sources": {"text": text_run.name, "vision": vision_run.name},
            "source_sha256": {
                "text_raw": sha256(text_run / "raw.jsonl"),
                "vision_raw": sha256(vision_run / "raw.jsonl"),
            },
            "counts": {
                "observations": len(obs),
                "models": len(models),
                "tasks": len({o["task"] for o in obs}),
            },
        },
        "models": sorted(models.values(), key=lambda m: m["slug"]),
        "observations": sorted(obs, key=lambda o: o["id"]),
        "text_summary": json.loads((text_run / "summary.json").read_text(encoding="utf-8")),
        "vision_summary": vision_summary,
        "vision_tasks": vision_cards(vision_run),
        "catalog": load_catalog(),
        "local": local_results(),
        "verify": verify,
        "claims": claims,
    }
    return data


def validate_claims(claims: list[dict]) -> list[str]:
    problems = []
    seen = set()
    for c in claims:
        cid = c.get("id", "?")
        if cid in seen:
            problems.append(f"{cid}: duplicate id")
        seen.add(cid)
        if c.get("status") not in STATUSES:
            problems.append(f"{cid}: bad status {c.get('status')!r}")
        if not (c.get("evidence") or "").strip():
            problems.append(f"{cid}: empty evidence")
        if not (c.get("quote") or "").strip():
            problems.append(f"{cid}: empty quote")
    return problems


# --------------------------------------------------------------------- render
def render_html(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")
    if len(payload.encode("utf-8")) > 2_000_000:
        raise SystemExit("payload exceeds 2 MB")

    template = (WEB / "template.html").read_text(encoding="utf-8")
    css = (WEB / "app.css").read_text(encoding="utf-8")
    js = (WEB / "app.js").read_text(encoding="utf-8")
    html = (template
            .replace("/*__CSS__*/", css)
            .replace("/*__JS__*/", js)
            .replace("__PAYLOAD__", payload))
    return html


def cmd_build(args) -> int:
    data = build_data()
    html = render_html(data)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "data.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    out = REPORTS / "index.html"
    out.write_bytes(html.encode("utf-8"))
    print(f"built: {out}  ({len(html.encode('utf-8')) / 1024:.0f} KB, "
          f"{len(data['observations'])} observations, "
          f"{data['meta']['counts']['models']} models)")
    print(f"payload sha256: {hashlib.sha256(html.encode()).hexdigest()[:32]}")
    return 0


def cmd_check(args) -> int:
    """Provenance invariant: recomputed accuracy must match summary.json."""
    data = build_data()
    text_run = latest_run("run")
    summary = json.loads((text_run / "summary.json").read_text(encoding="utf-8"))
    failures = []
    for slug, entry in summary["models"].items():
        rows = [o for o in data["observations"] if o["model"] == slug and o["test"] == "text"]
        acc = sum(o["ok"] for o in rows if o["ok"] is not None) / len(rows)
        delta = abs(acc - entry["accuracy"])
        status = "ok" if delta <= 1e-9 else "MISMATCH"
        print(f"{slug:<42} report={acc:.6f} summary={entry['accuracy']:.6f} {status}")
        if delta > 1e-9:
            failures.append(slug)

    vision_run = latest_run("vision")
    vsummary = json.loads((vision_run / "summary.json").read_text(encoding="utf-8"))
    for slug, entry in vsummary["models"].items():
        rows = [o for o in data["observations"] if o["model"] == slug and o["test"] == "vision"]
        scored = [o for o in rows if o["ok"] is not None]
        acc = sum(o["ok"] for o in scored) / len(scored) if scored else 0
        if abs(acc - entry["accuracy"]) > 1e-9:
            failures.append(slug)
            print(f"{slug:<42} vision report={acc:.6f} summary={entry['accuracy']:.6f} MISMATCH")
        else:
            print(f"{slug:<42} vision report={acc:.6f} summary={entry['accuracy']:.6f} ok")

    bad = [o["id"] for o in data["observations"] if o["p"] is None and not o["skip"] and o["test"] == "text"]
    if bad:
        failures.append(f"{len(bad)} observations without p")
    print(f"\nobservations={len(data['observations'])} failures={len(failures)}")
    return 1 if failures else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalog").set_defaults(func=lambda a: refresh_catalog() and 0)
    sub.add_parser("build").set_defaults(func=cmd_build)
    sub.add_parser("check").set_defaults(func=cmd_check)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
