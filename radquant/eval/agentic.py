"""RadQuant clinical reasoning agent — MedGemma as the visual brain (Phase 8+).

Unlike the first (failed) design where a *blind* text LLM relayed MedGemma's
descriptions, here MedGemma itself sees the figures and runs a structured,
radiologist-style loop:

    perceive  -> list grounded findings from the image(s)
    deliberate/decide -> weigh the options against those findings, commit, and
                         SELF-RATE confidence (High/Medium/Low)

The confidence output is the substrate for selective prediction (abstention):
RadQuant answers confidently or defers the case to the radiologist. This is the
genuine contribution — a system that knows when it doesn't know.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import List, Optional, Tuple

from radquant.eval.chestagentbench import RESULTS_DIR, Scoreboard, extract_letter
from radquant.eval.direct import MAX_FIGURES, figure_label

PERCEIVE_SYSTEM = (
    "You are an expert thoracic radiologist examining the figure(s). Describe only "
    "what you actually see."
)
DECIDE_SYSTEM = (
    "You are an expert thoracic radiologist answering a board-style multiple-choice "
    "question. Reason from the observations and the image(s)."
)

PERCEIVE_PROMPT = (
    "List the salient radiological findings in the figure(s): for each, the finding, "
    "its location/laterality, and severity. Be specific and concise (bullet list)."
)

_CONF_RE = re.compile(r"confidence\s*[:\-]?\s*(high|medium|low)", re.IGNORECASE)


def _decide_prompt(question: str, observations: str) -> str:
    return (
        f"{question}\n\nYour own observations of the figure(s):\n{observations}\n\n"
        "Weigh each option against the image and your observations. Then end with "
        "EXACTLY two lines:\nAnswer: X   (a single option letter)\n"
        "Confidence: High|Medium|Low   (how sure you are)"
    )


def parse_confidence(text: str) -> str:
    m = _CONF_RE.findall(text or "")
    return m[-1].capitalize() if m else "Medium"


def agent_answer(mg, record: dict, classifier_hint: bool = False
                 ) -> Tuple[Optional[str], str, str]:
    """Run perceive→decide. Returns (letter, confidence, raw_decision)."""
    imgs = record["image_paths"][:MAX_FIGURES]
    labels = [figure_label(p) for p in imgs]

    perceive = PERCEIVE_PROMPT
    if classifier_hint:
        from radquant.nodes.classify import classify_image
        try:
            preds = classify_image(imgs[0])
            top = ", ".join(f"{k} {v:.2f}" for k, v in
                            sorted(preds.items(), key=lambda kv: kv[1], reverse=True)[:3])
            perceive += f"\n(An automated classifier suggested, possibly unreliably: {top}.)"
        except Exception:  # noqa: BLE001
            pass

    observations = mg.generate_multi(imgs, perceive, labels=labels,
                                     system=PERCEIVE_SYSTEM, max_new_tokens=256)
    decision = mg.generate_multi(imgs, _decide_prompt(record["question"], observations),
                                 labels=labels, system=DECIDE_SYSTEM, max_new_tokens=384)
    return extract_letter(decision), parse_confidence(decision), decision


def run_agentic(records: List[dict], tag: str = "agentic", classifier_hint: bool = False,
                every: int = 5) -> Scoreboard:
    """Resumable agentic eval with a live scoreboard; stores confidence for abstention."""
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
    print(f"AGENTIC eval: {len(todo)} of {len(records)} (classifier={classifier_hint})\n")

    mg = get_medgemma()
    target = board.total + len(todo)
    with path.open("a") as out:
        for rec in todo:
            t0 = time.time()
            try:
                pred, conf, raw = agent_answer(mg, rec, classifier_hint=classifier_hint)
                err = None
            except Exception as e:  # noqa: BLE001
                pred, conf, raw, err = None, "Low", "", str(e)[:160]
            correct = (pred or "") == rec["answer"].upper()
            board.update(rec["categories"], correct)

            row = {"full_question_id": rec["full_question_id"],
                   "categories": rec["categories"], "gold": rec["answer"],
                   "pred": pred, "confidence": conf, "correct": correct,
                   "seconds": round(time.time() - t0, 1), "raw": raw[:300]}
            if err:
                row["error"] = err
            out.write(json.dumps(row) + "\n")
            out.flush()

            mark = "✓" if correct else "✗"
            print(f"[{board.total:4d}/{target}] {mark} gold={rec['answer']} "
                  f"pred={pred or '—'} conf={conf:6} {board.line(target)}")
            if board.total % every == 0:
                print(board.table())
    print("\nFINAL:")
    print(board.table())
    return board
