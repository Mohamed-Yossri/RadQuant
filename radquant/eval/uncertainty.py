"""Uncertainty via answer-agreement — the basis for RadQuant's selective prediction.

The PREDICTION stays our best method (greedy multi-image CoT, ~57.6%). For each
case we additionally sample the reasoning K times at temperature; the CONFIDENCE
is how often those samples agree with the greedy answer. High agreement ⇒ the
model is genuinely sure ⇒ high accuracy. Low agreement ⇒ defer to the radiologist.

We reuse the greedy answers already computed in run_direct_cot.jsonl, so this only
needs the K extra samples per case.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from radquant.eval.chestagentbench import RESULTS_DIR, extract_letter
from radquant.eval.direct import MAX_FIGURES, build_prompt, figure_label, DIRECT_SYSTEM

GREEDY_FILE = RESULTS_DIR / "run_direct_cot.jsonl"


def _load_greedy() -> Dict[str, dict]:
    """{full_question_id: greedy_row} from the direct-CoT run (the prediction)."""
    if not GREEDY_FILE.exists():
        return {}
    return {json.loads(l)["full_question_id"]: json.loads(l) for l in GREEDY_FILE.open()}


def sample_letters(mg, record: dict, k: int, max_new_tokens: int = 512) -> List[str]:
    """Generate K sampled answers (temp 0.7) and return their option letters."""
    imgs = record["image_paths"][:MAX_FIGURES]
    labels = [figure_label(p) for p in imgs]
    prompt = build_prompt(record["question"], cot=True, classifier_hint=None)
    out = []
    for _ in range(k):
        raw = mg.generate_multi(imgs, prompt, labels=labels, system=DIRECT_SYSTEM,
                                max_new_tokens=max_new_tokens, do_sample=True, temperature=0.7)
        letter = extract_letter(raw)
        if letter:
            out.append(letter)
    return out


def run_uncertainty(records: List[dict], k: int = 4, tag: str = "uncertainty",
                    every: int = 10):
    """For each record: reuse greedy answer, add K samples, store agreement."""
    from radquant.models import get_medgemma

    greedy = _load_greedy()
    records = [r for r in records if r["full_question_id"] in greedy]
    if not records:
        raise SystemExit("No greedy answers found — run `--direct` first.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"run_{tag}.jsonl"
    done = {json.loads(l)["full_question_id"] for l in path.open()} if path.exists() else set()
    todo = [r for r in records if r["full_question_id"] not in done]
    print(f"UNCERTAINTY: {len(todo)} of {len(records)} cases, k={k} samples each\n")

    mg = get_medgemma()
    t0 = time.time()
    with path.open("a") as out:
        for i, rec in enumerate(todo, 1):
            g = greedy[rec["full_question_id"]]
            gp = g.get("pred")
            try:
                samples = sample_letters(mg, rec, k)
                agree = (sum(1 for s in samples if s == gp) / len(samples)
                         if samples else 0.0)
            except Exception as e:  # noqa: BLE001
                samples, agree = [], 0.0
            row = {"full_question_id": rec["full_question_id"],
                   "categories": rec["categories"], "gold": rec["answer"],
                   "pred": gp, "correct": bool(g.get("correct")),
                   "agreement": round(agree, 3), "n_samples": len(samples)}
            out.write(json.dumps(row) + "\n")
            out.flush()
            if i % every == 0 or i == len(todo):
                el = time.time() - t0
                print(f"[{i:4d}/{len(todo)}] agree={agree:.2f} "
                      f"| {el/i:4.1f}s/case | eta {(el/i)*(len(todo)-i)/60:4.1f}m")
    print(f"\n✓ done → {path}")
    return path
