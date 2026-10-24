"""Print model-vs-gold mismatches for one run, so corpus bugs can be spotted.

    python -m src.mismatches --run runs/<id> --family choice_fact
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.runner import build_summary, read_raw  # noqa: E402
from src.tasks import load  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--family")
    args = ap.parse_args(argv)

    run = Path(args.run)
    latest: dict = {}
    for row in read_raw(run / "raw.jsonl"):
        latest[(row["model"], row["task_id"])] = row
    tasks = {t["id"]: t for t in load()}

    by_task: dict[str, list[str]] = {}
    for (model, task_id), row in latest.items():
        if not row.get("ok"):
            continue
        task = tasks[task_id]
        if args.family and task["family"] != args.family:
            continue
        for qid, spec in task["questions"].items():
            ans = row["answers"][qid]
            gold = task["gold"][qid]
            if spec["type"] == "choice":
                ok = ans["value"] == gold
                pred = ans["value"]
                conf = ans.get("confidence")
            elif spec["type"] == "noul":
                ok = (ans["value"] >= 0.5) == gold
                pred = ans["value"]
                conf = max(ans["value"], 1 - ans["value"])
            else:
                ok = round(ans["value"]) == gold
                pred = round(ans["value"], 2)
                conf = ans.get("confidence")
            if not ok:
                by_task.setdefault(task_id, []).append(
                    f"{model.split('/')[-1]:<24} pred={pred!r:<22} conf={conf if conf is None else round(conf, 3)}"
                )

    for task_id, lines in sorted(by_task.items()):
        task = tasks[task_id]
        qid = next(iter(task["questions"]))
        print(f"\n{task_id}  [{task['family']}]  gold={task['gold'][qid]!r}")
        print(f"  {task['rationale']}")
        for line in lines:
            print("  " + line)
    print(f"\n{len(by_task)} tasks with at least one mismatch")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
