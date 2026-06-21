"""Direct multi-image VLM evaluation on ChestAgentBench (Phase 8, Experiment 1+).

Instead of a blind text orchestrator relaying MedGemma's descriptions, we let
MedGemma SEE all the figures and answer the multiple-choice question itself.
Supports chain-of-thought, an optional classifier hint, and self-consistency
voting — each togglable so we can measure the delta.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

from radquant.eval.chestagentbench import (
    RESULTS_DIR, Scoreboard, extract_letter,
)

DIRECT_SYSTEM = (
    "You are an expert radiologist answering a board-style multiple-choice "
    "question about the medical figure(s) shown. Look at the image(s) carefully "
    "and reason from what you actually see."
)

MAX_FIGURES = 6  # cap interleaved images for VRAM/latency on the L4


def figure_label(path: str) -> str:
    """'.../figure_2a.jpg' -> 'Figure 2A' (aligns with how questions cite figures)."""
    m = re.search(r"figure[_-]?([0-9]+[a-z]?)", Path(path).stem, re.I)
    return f"Figure {m.group(1).upper()}" if m else Path(path).stem


def build_prompt(question: str, cot: bool, classifier_hint: Optional[str],
                 answer_first: bool = False) -> str:
    hint = (f"\n\nAutomated classifier hint (may be unreliable): {classifier_hint}"
            if classifier_hint else "")
    if answer_first:
        tail = ("\n\nOn the FIRST line write exactly 'Answer: X' (your single best "
                "option letter). Then briefly justify it in 1-2 sentences.")
    elif cot:
        tail = ("\n\nLook at the figure(s). In AT MOST 3 short sentences, give the key "
                "reason for your choice. Then, on the LAST line, write exactly "
                "'Answer: X' (a single option letter). Do not omit that line.")
    else:
        tail = "\n\nRespond with ONLY this line:\nAnswer: X"
    return question + hint + tail


def _classifier_hint(image_paths: List[str]) -> Optional[str]:
    from radquant.nodes.classify import classify_image
    try:
        preds = classify_image(image_paths[0])
        top = sorted(preds.items(), key=lambda kv: kv[1], reverse=True)[:3]
        return ", ".join(f"{k} {v:.2f}" for k, v in top)
    except Exception:  # noqa: BLE001
        return None


def answer_direct(mg, record: dict, cot: bool = True, with_classifier: bool = False,
                  answer_first: bool = False, k: int = 1, pan_and_scan: bool = False,
                  max_new_tokens: int = 512) -> Tuple[Optional[str], str]:
    """Answer one record with MedGemma directly. Returns (letter, raw_first_sample)."""
    imgs = record["image_paths"][:MAX_FIGURES]
    labels = [figure_label(p) for p in imgs]
    hint = _classifier_hint(imgs) if with_classifier else None
    prompt = build_prompt(record["question"], cot, hint, answer_first=answer_first)

    votes: List[str] = []
    first_raw = ""
    for s in range(k):
        raw = mg.generate_multi(
            imgs, prompt, labels=labels, system=DIRECT_SYSTEM,
            max_new_tokens=max_new_tokens,
            do_sample=(k > 1), temperature=0.7, pan_and_scan=pan_and_scan,
        )
        if s == 0:
            first_raw = raw
        letter = extract_letter(raw)
        if letter:
            votes.append(letter)
    if not votes:
        return None, first_raw
    return Counter(votes).most_common(1)[0][0], first_raw


def run_direct(records: List[dict], tag: str = "direct", cot: bool = True,
               with_classifier: bool = False, answer_first: bool = False,
               k: int = 1, pan_and_scan: bool = False, every: int = 5) -> Scoreboard:
    """Resumable direct-VLM eval with a live scoreboard. Stores raw output to audit."""
    from radquant.models import get_medgemma

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"run_{tag}.jsonl"
    done = {json.loads(l)["full_question_id"] for l in path.open()} if path.exists() else set()

    board = Scoreboard()
    if done:
        for l in path.open():
            r = json.loads(l)
            board.update(r.get("categories", []), r.get("correct", False))
        print(f"resuming: {len(done)} scored — {board.line(len(records))}")

    todo = [r for r in records if r["full_question_id"] not in done]
    print(f"DIRECT eval: {len(todo)} of {len(records)} "
          f"(cot={cot}, classifier={with_classifier}, k={k})\n")

    mg = get_medgemma()
    target = board.total + len(todo)
    with path.open("a") as out:
        for rec in todo:
            t0 = time.time()
            try:
                pred, raw = answer_direct(mg, rec, cot=cot,
                                          with_classifier=with_classifier,
                                          answer_first=answer_first, k=k,
                                          pan_and_scan=pan_and_scan)
                err = None
            except Exception as e:  # noqa: BLE001
                pred, raw, err = None, "", str(e)[:160]
            correct = (pred or "") == rec["answer"].upper()
            board.update(rec["categories"], correct)

            row = {"full_question_id": rec["full_question_id"],
                   "categories": rec["categories"], "gold": rec["answer"],
                   "pred": pred, "correct": correct, "seconds": round(time.time() - t0, 1),
                   "raw": raw[:400]}
            if err:
                row["error"] = err
            out.write(json.dumps(row) + "\n")
            out.flush()

            mark = "✓" if correct else "✗"
            print(f"[{board.total:4d}/{target}] {mark} gold={rec['answer']} "
                  f"pred={pred or '—'}  {board.line(target)}")
            if board.total % every == 0:
                print(board.table())
    print("\nFINAL:")
    print(board.table())
    return board
