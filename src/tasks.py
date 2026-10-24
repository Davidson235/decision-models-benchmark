"""Load and validate the task corpus.

Validation is deliberately strict: a malformed gold label would silently
poison every metric downstream, so loading fails loudly instead.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.corpus_a import TASKS_A  # noqa: E402
from data.corpus_b import TASKS_B  # noqa: E402
from data.corpus_c import TASKS_C_ADVERSARIAL, TASKS_C_MULTILINGUAL  # noqa: E402

ALL_TASKS: list[dict] = TASKS_A + TASKS_B + TASKS_C_ADVERSARIAL + TASKS_C_MULTILINGUAL

VALID_TYPES = {"choice", "noul", "score"}
REQUIRED = {"id", "family", "domain", "lang", "difficulty", "state", "questions", "gold", "rationale"}


class TaskError(ValueError):
    pass


def validate(tasks: list[dict]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for t in tasks:
        missing = REQUIRED - set(t)
        if missing:
            problems.append(f"{t.get('id', '?')}: missing fields {sorted(missing)}")
            continue
        tid = t["id"]
        if tid in seen:
            problems.append(f"{tid}: duplicate id")
        seen.add(tid)
        if not isinstance(t["state"], (str, dict, list)):
            problems.append(f"{tid}: state must be str/dict/list")
        if not t["questions"]:
            problems.append(f"{tid}: no questions")
        if set(t["questions"]) != set(t["gold"]):
            problems.append(f"{tid}: questions/gold key mismatch")
        for qid, spec in t["questions"].items():
            qtype = spec.get("type")
            if qtype not in VALID_TYPES:
                problems.append(f"{tid}.{qid}: bad type {qtype!r}")
                continue
            if not spec.get("instructions"):
                problems.append(f"{tid}.{qid}: empty instructions")
            criteria = spec.get("criteria")
            if qtype == "choice":
                if not isinstance(criteria, dict) or len(criteria) < 2:
                    problems.append(f"{tid}.{qid}: choice needs >=2 criteria")
                elif t["gold"][qid] not in criteria:
                    problems.append(f"{tid}.{qid}: gold not among options")
            elif qtype == "noul":
                if not isinstance(criteria, dict) or set(criteria) != {"true", "false"}:
                    problems.append(f"{tid}.{qid}: noul criteria must be true/false")
                if not isinstance(t["gold"][qid], bool):
                    problems.append(f"{tid}.{qid}: noul gold must be bool")
            elif qtype == "score":
                if not isinstance(criteria, list) or len(criteria) < 2:
                    problems.append(f"{tid}.{qid}: score needs a list of levels")
                gold = t["gold"][qid]
                if not isinstance(gold, int) or not (0 <= gold < len(criteria or [])):
                    problems.append(f"{tid}.{qid}: score gold {gold!r} outside 0..{len(criteria or []) - 1}")
    return problems


def load(validate_only: bool = False) -> list[dict]:
    problems = validate(ALL_TASKS)
    if problems:
        raise TaskError("corpus validation failed:\n  " + "\n  ".join(problems))
    return ALL_TASKS


def counts(tasks: list[dict]) -> dict:
    out: dict[str, int] = {}
    for t in tasks:
        out[t["family"]] = out.get(t["family"], 0) + 1
    return out


def dump_jsonl(path: Path) -> int:
    tasks = load()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for t in tasks:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    return len(tasks)


if __name__ == "__main__":
    tasks = load()
    print(f"tasks: {len(tasks)}")
    for family, n in sorted(counts(tasks).items()):
        print(f"  {family:<22} {n}")
    questions = sum(len(t["questions"]) for t in tasks)
    print(f"questions: {questions}")
    langs: dict[str, int] = {}
    for t in tasks:
        langs[t["lang"]] = langs.get(t["lang"], 0) + 1
    print(f"languages: {langs}")
