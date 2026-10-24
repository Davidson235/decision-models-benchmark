"""The five self-checks from the plan, executable.

    python -m src.verify

Each check prints PASS/FAIL and the process exits non-zero if any check fails.
Checks 3-4 spend real API quota (~20 calls).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import metrics  # noqa: E402
from src.client import Client  # noqa: E402
from src.normalizer import normalize  # noqa: E402
from src.runner import RUNS, build_payload, build_summary, read_raw  # noqa: E402
from src.tasks import load  # noqa: E402

PY = sys.executable
results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))

def _call(client, payload, tries: int = 3):
    """One request with a coarse retry, so a burst of 429s cannot fail a check."""
    import time

    last = None
    for attempt in range(tries):
        try:
            return client.call(payload, use_cache=False)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < tries - 1:
                time.sleep(5 * (attempt + 1))
    raise last


# 1 ---------------------------------------------------------------------------
def check_unit_tests() -> bool:
    ok = True
    for script in ("tests/test_metrics.py", "tests/test_normalizer.py"):
        proc = subprocess.run([PY, str(ROOT / script)], capture_output=True, text=True)
        passed = proc.returncode == 0
        ok &= passed
        tail = (proc.stdout or proc.stderr).strip().splitlines()[-1:]
        print(f"      {script}: {'ok' if passed else 'FAILED'} {tail}")
    return ok


# 2 ---------------------------------------------------------------------------
def check_contract_replay() -> bool:
    recorded = [
        {"answers": {"q": {"type": "noul", "noul": 0.93}}},
        {"answers": {"q": {"type": "choice", "choice": "b",
                           "probabilities": {"a": 0.2, "b": 0.8}, "confidence": 0.8}}},
        {"answers": {"q": {"type": "score", "score": 1.5,
                           "probabilities": {"0": 0.1, "1": 0.3, "2": 0.6},
                           "legend": {"0": "a", "1": "b", "2": "c"}}}},
    ]
    try:
        out = [normalize(r)["q"] for r in recorded]
    except Exception as exc:  # noqa: BLE001
        print(f"      replay raised: {exc}")
        return False
    good = (
        abs(out[0]["value"] - 0.93) < 1e-12
        and out[1]["value"] == "b"
        and abs(out[2]["value"] - 1.5) < 1e-12
        and list(out[2]["probs"]) == [0, 1, 2]
    )
    # malformed body must raise, not silently produce zeros
    try:
        normalize({"answers": {"q": {"type": "choice", "probabilities": {"a": 0.1}}}})
        loud = False
    except Exception:  # noqa: BLE001
        loud = True
    return good and loud


# 3 ---------------------------------------------------------------------------
def check_live_smoke() -> bool:
    tasks = load()[:3]
    client = Client(min_interval=0.2, cache_dir=None)
    ok = True
    for task in tasks:
        try:
            resp, meta = _call(client, build_payload("baseten/elephant-1:free", task))
            answers = normalize(resp)
            usage = resp.get("usage") or {}
            probs = [sum(a["probs"].values()) for a in answers.values() if a.get("probs")]
            sums_ok = all(abs(p - 1.0) < 1e-6 for p in probs)
            good = bool(answers) and sums_ok and "cost" in usage and meta["latency_ms"] > 0
            ok &= good
            print(f"      {task['id']}: answers={len(answers)} sums_ok={sums_ok} "
                  f"cost={usage.get('cost')} out_tok={usage.get('output_tokens')} "
                  f"latency={meta['latency_ms']}ms")
        except Exception as exc:  # noqa: BLE001
            print(f"      {task['id']}: raised {exc}")
            ok = False
    return ok


# 4 ---------------------------------------------------------------------------
def check_determinism() -> bool:
    tasks = load()[10:15]
    client = Client(min_interval=0.2, cache_dir=None)
    worst = 0.0
    for task in tasks:
        payload = build_payload("baseten/mammoth-1:free", task)
        try:
            a = normalize(_call(client, payload)[0])
            b = normalize(_call(client, payload)[0])
        except Exception as exc:  # noqa: BLE001
            print(f"      {task['id']}: raised {exc}")
            return False
        for qid in a:
            pa, pb = a[qid].get("probs") or {}, b[qid].get("probs") or {}
            for key in set(pa) | set(pb):
                worst = max(worst, abs(float(pa.get(key, 0)) - float(pb.get(key, 0))))
    print(f"      max |delta p| over 5 tasks x 2 runs = {worst:.3e}")
    return worst < 1e-9


def check_resume() -> bool:
    """Two tasks, then resume with four: 4 unique rows, no duplicates."""
    import os

    run_dir = Path(tempfile.mkdtemp(prefix="resume-", dir=RUNS))
    env = {**os.environ}
    cmd = [PY, "-m", "src.runner", "run", "--models", "baseten/elephant-1:free",
           "--run", str(run_dir)]
    subprocess.run(cmd + ["--limit", "2"], cwd=ROOT, env=env, capture_output=True, text=True)
    first = read_raw(run_dir / "raw.jsonl")
    subprocess.run(cmd + ["--limit", "4"], cwd=ROOT, env=env, capture_output=True, text=True)
    rows = read_raw(run_dir / "raw.jsonl")
    keys = [(r["model"], r["task_id"], r.get("repeat", 0)) for r in rows]
    ok = len(first) == 2 and len(rows) == 4 and len(set(keys)) == 4
    print(f"      first={len(first)} after_resume={len(rows)} unique={len(set(keys))}")
    return ok


# 5 ---------------------------------------------------------------------------
def check_audit() -> bool:
    candidates = sorted(p for p in RUNS.glob("run-*") if (p / "raw.jsonl").exists())
    if not candidates:
        print("      no completed run found")
        return False
    run_dir = candidates[-1]
    raw_rows = read_raw(run_dir / "raw.jsonl")
    # Retried rows are appended; only the last attempt per key counts.
    latest: dict[tuple, dict] = {}
    for row in raw_rows:
        latest[(row["model"], row["task_id"], row.get("repeat", 0))] = row
    rows = list(latest.values())
    tasks = {t["id"] for t in load()}
    models = {r["model"] for r in rows}
    covered = {(r["model"], r["task_id"]) for r in rows}
    failures = [r for r in rows if not r.get("ok")]
    expected = len(tasks) * len(models)

    summary = build_summary(run_dir)
    payload = json.dumps(summary, ensure_ascii=False, indent=2).encode("utf-8")
    (run_dir / "summary.json").write_bytes(payload)
    scored = sum(e.get("n", 0) for e in summary["models"].values())

    summary2 = build_summary(run_dir)
    data2 = json.dumps(summary2, ensure_ascii=False, indent=2).encode("utf-8")
    deterministic = hashlib.sha256(payload).hexdigest() == hashlib.sha256(data2).hexdigest()

    ok = (
        len(covered) == expected
        and not failures
        and scored == expected
        and deterministic
    )
    print(f"      run={run_dir.name} raw_rows={len(raw_rows)} unique_pairs={len(covered)} "
          f"expected={expected} failures={len(failures)} scored={scored} "
          f"summary_deterministic={deterministic}")
    return ok


CHECKS = [
    ("1. metrics + normalizer unit tests", check_unit_tests),
    ("2. contract replay (3 shapes + malformed)", check_contract_replay),
    ("3. live smoke (3 tasks, real key)", check_live_smoke),
    ("4a. determinism (5 tasks x 2)", check_determinism),
    ("4b. resume without duplicates", check_resume),
    ("5. full-run audit + deterministic summary", check_audit),
]


def main() -> int:
    if not __import__("os").environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set; checks 3-4b will fail")
    for name, fn in CHECKS:
        print(f"\n== {name}")
        try:
            ok = fn()
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"      raised {type(exc).__name__}: {exc}")
        record(name, bool(ok))

    failed = [n for n, ok, _ in results if not ok]
    payload = [{"name": n, "ok": bool(ok), "detail": d} for n, ok, d in results]
    RUNS.mkdir(exist_ok=True)
    (RUNS / "verify.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nwritten: {RUNS / 'verify.json'}")
    print("=" * 60)
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("failed: " + "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
