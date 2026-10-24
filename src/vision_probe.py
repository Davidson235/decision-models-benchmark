"""Check empirically which decision models actually read images, and whether
the Box primitive returns usable coordinates.

    python -m src.vision_probe

Builds a synthetic PNG (white canvas, red square in the lower-left area),
sends it as an `image_url` part inside `state`, and asks a Noul, a Choice and a
Box question. Prints the typed answers per model.
"""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from src.client import ApiError, Client  # noqa: E402
from src.normalizer import NormalizationError, normalize  # noqa: E402

MODELS = [
    "inception/mercury-decide:free",
    "typesafe/jev-1.14",
    "perplexity/pplx-decider-flash-v1.2",
    "cloudflare/clef-flash",
    "baseten/mammoth-1:free",  # text-only control
]


def make_image() -> str:
    """White 320x320 canvas with a red 80x80 square in the lower-left quadrant."""
    img = Image.new("RGB", (320, 320), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([40, 200, 120, 280], fill=(220, 20, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    image_part = {"type": "image_url", "image_url": {"url": make_image()}}
    state = [
        "Screenshot of a simple drawing. The red element is the only coloured object.",
        image_part,
    ]
    questions = {
        "has_red": {
            "type": "noul",
            "instructions": "Does the image contain a red object?",
            "criteria": {"true": "A red object is visible", "false": "No red object"},
        },
        "where": {
            "type": "choice",
            "instructions": "In which quadrant is the red object?",
            "criteria": {
                "top_left": "upper-left",
                "top_right": "upper-right",
                "bottom_left": "lower-left",
                "bottom_right": "lower-right",
            },
        },
        "box": {
            "type": "box",
            "instructions": "Locate the red square.",
        },
    }
    client = Client(min_interval=0.3, cache_dir=None)
    for model in MODELS:
        # Box questions are a Jev-only primitive; sending them to any other
        # model returns 400 before the image is even looked at.
        model_questions = dict(questions)
        if "jev" not in model:
            model_questions.pop("box")
        payload = {"model": model, "state": state, "questions": model_questions}
        try:
            resp, meta = client.call(payload, use_cache=False)
            answers = normalize(resp)
            print(f"\n{model}  [{meta['latency_ms']:.0f} ms, ${resp.get('usage', {}).get('cost', 0)}]")
            for qid, ans in answers.items():
                if ans["type"] == "noul":
                    print(f"   {qid}: p(yes) = {ans['value']:.3f}")
                elif ans["type"] == "choice":
                    print(f"   {qid}: {ans['value']}  probs={ {k: round(v, 3) for k, v in ans['probs'].items()} }")
                else:
                    print(f"   {qid}: raw = {json.dumps(ans, ensure_ascii=False)[:200]}")
        except (ApiError, NormalizationError) as exc:
            print(f"\n{model}  FAILED: {str(exc)[:220]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
