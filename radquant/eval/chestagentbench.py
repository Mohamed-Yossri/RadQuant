"""ChestAgentBench evaluation harness (Phase 8).

Drives the RadQuant agent over the benchmark's multiple-choice questions, scores
predictions against the gold letter, and tracks a LIVE running accuracy (overall
+ per-category). Designed to be watched and stopped early: results stream to a
JSONL file and a re-run resumes where it left off.
"""

from __future__ import annotations

import json
import random
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from radquant.config import DATA_DIR

BENCH_DIR = DATA_DIR / "chestagentbench"
METADATA = BENCH_DIR / "metadata.jsonl"
RESULTS_DIR = DATA_DIR / "eval_results"

# The 7 ChestAgentBench skill categories (the metadata also tags "reasoning",
# which appears on every question, so it is not one of the 7 scored skills).
CATEGORIES = ["detection", "classification", "localization", "comparison",
              "relationship", "diagnosis", "characterization"]

EVAL_SYSTEM_PROMPT = (
    "You answer multiple-choice questions about chest X-ray figures. You CANNOT "
    "see images yourself — you must call the `medgemma` tool (pass an `image_path` "
    "and a specific visual question) to inspect a figure, and you may call "
    "`chest_xray_classifier` (pass an `image_path`) for pathology probabilities. "
    "Inspect the relevant figure(s), weigh the options, then finish with a line "
    "in exactly this form: 'Answer: X' where X is the single best option letter."
)

# Ordered extraction patterns (first non-empty match wins; take its LAST hit).
_EXTRACT_PATTERNS = [
    r"answer\s*(?:is|:|=|-|\)?\s*is)?\s*\*{0,2}\(?([A-Fa-f])\)?",   # "Answer: B", "answer is B"
    r"(?:option|choice)\s*\(?([A-Fa-f])\)?",                        # "option B"
    r"\(?([A-Fa-f])\)?\s+is\s+(?:the\s+)?(?:correct|best|right)",   # "B is correct"
    r"\*\*\(?([A-F])\)?[\).:]",                                     # "**B)**"
]


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def load_records(limit: Optional[int] = None, stratified: bool = False,
                 seed: int = 0) -> List[dict]:
    """Load benchmark records with absolute image paths.

    stratified: round-robin across the primary category for a representative
    calibration batch (otherwise a fixed-seed random sample).
    """
    recs = []
    for line in METADATA.open():
        r = json.loads(line)
        r["categories"] = [c.strip() for c in r.get("categories", "").split(",") if c.strip()]
        r["image_paths"] = [str(BENCH_DIR / p) for p in r.get("images", [])]
        recs.append(r)

    if limit is None:
        return recs

    rng = random.Random(seed)
    if stratified:
        groups: Dict[str, List[dict]] = defaultdict(list)
        for r in recs:
            primary = next((c for c in r["categories"] if c in CATEGORIES), "other")
            groups[primary].append(r)
        for g in groups.values():
            rng.shuffle(g)
        out, keys = [], [k for k in CATEGORIES if k in groups]
        i = 0
        while len(out) < limit and any(groups[k] for k in keys):
            k = keys[i % len(keys)]
            if groups[k]:
                out.append(groups[k].pop())
            i += 1
        return out[:limit]

    rng.shuffle(recs)
    return recs[:limit]


def extract_letter(text: str) -> Optional[str]:
    """Pull the chosen option letter out of a model answer (robust to CoT)."""
    if not text:
        return None
    for pat in _EXTRACT_PATTERNS:
        hits = re.findall(pat, text, re.IGNORECASE)
        if hits:
            return hits[-1].upper()
    tail = re.findall(r"\b([A-F])\b", text[-60:])  # last standalone A-F near the end
    return tail[-1].upper() if tail else None


# --------------------------------------------------------------------------- #
# live scoreboard
# --------------------------------------------------------------------------- #
class Scoreboard:
    """Running overall + per-category accuracy, fed one result at a time."""

    def __init__(self):
        self.total = self.correct = 0
        self.cat = defaultdict(lambda: [0, 0])  # cat -> [correct, total]
        self.t0 = time.time()

    def update(self, categories: List[str], correct: bool) -> None:
        self.total += 1
        self.correct += int(correct)
        for c in categories:
            if c in CATEGORIES:
                self.cat[c][1] += 1
                self.cat[c][0] += int(correct)

    def overall(self) -> float:
        return self.correct / self.total if self.total else 0.0

    def line(self, n_target: int) -> str:
        elapsed = time.time() - self.t0
        rate = elapsed / self.total if self.total else 0
        eta = rate * (n_target - self.total)
        return (f"overall {self.overall()*100:5.1f}%  ({self.correct}/{self.total})  "
                f"| {rate:4.1f}s/q | elapsed {elapsed/60:4.1f}m | eta {eta/60:5.1f}m")

    def table(self) -> str:
        rows = ["  per-category accuracy:"]
        for c in CATEGORIES:
            cor, tot = self.cat[c]
            acc = f"{cor/tot*100:5.1f}%" if tot else "  n/a"
            rows.append(f"    {c:16} {acc}  ({cor}/{tot})")
        return "\n".join(rows)


# --------------------------------------------------------------------------- #
# agent
# --------------------------------------------------------------------------- #
def build_eval_agent(backend: str = "nvidia", medgemma_cap: int = 160):
    from radquant.foundation import build_agent

    agent, tools = build_agent(
        tools_to_use=["MedGemmaVQATool", "ChestXRayClassifierTool"],
        backend=backend,
        system_prompt=EVAL_SYSTEM_PROMPT,
        temperature=0.0,
        max_tokens=1024,
        log_tools=False,  # 2,500 queries x many tool calls — don't spam logs/
    )
    # Cap MedGemma generation length so multi-figure questions stay fast.
    if "medgemma" in tools:
        tools["medgemma"].max_tokens_cap = medgemma_cap
    return agent, tools


def answer_one(agent, record: dict, recursion_limit: int = 12) -> str:
    """Run the agent on one record and return its raw final answer text."""
    from langchain_core.messages import HumanMessage

    paths = "\n".join(f"  - {p}" for p in record["image_paths"])
    msg = (f"Figure image_path value(s) to inspect with the medgemma tool:\n{paths}\n\n"
           f"{record['question']}\n\n"
           "Inspect the figure(s) with the tools, then end with 'Answer: <letter>'.")
    result = agent.workflow.invoke(
        {"messages": [HumanMessage(content=msg)]},
        config={"configurable": {"thread_id": record["full_question_id"]},
                "recursion_limit": recursion_limit},
    )
    return result["messages"][-1].content or ""


# --------------------------------------------------------------------------- #
# resumable runner
# --------------------------------------------------------------------------- #
def _results_path(backend: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR / f"run_{backend}.jsonl"


def _done_ids(path: Path) -> set:
    if not path.exists():
        return set()
    return {json.loads(l)["full_question_id"] for l in path.open() if l.strip()}


def run(records: List[dict], backend: str = "nvidia", every: int = 5) -> Scoreboard:
    """Evaluate records with a live scoreboard; append results to JSONL (resumable)."""
    path = _results_path(backend)
    done = _done_ids(path)
    board = Scoreboard()

    # Replay already-done results into the board so resumed runs show true totals.
    if done:
        for l in path.open():
            r = json.loads(l)
            board.update(r.get("categories", []), r.get("correct", False))
        print(f"resuming: {len(done)} already scored — {board.line(len(records))}")

    todo = [r for r in records if r["full_question_id"] not in done]
    print(f"running {len(todo)} of {len(records)} (backend={backend})\n")

    agent, _ = build_eval_agent(backend)
    target = board.total + len(todo)

    with path.open("a") as out:
        for rec in todo:
            t0 = time.time()
            try:
                raw = answer_one(agent, rec)
                pred = extract_letter(raw)
                err = None
            except Exception as e:  # noqa: BLE001  (keep the run alive)
                pred, err = None, str(e)[:160]
            correct = (pred or "") == rec["answer"].upper()
            board.update(rec["categories"], correct)

            row = {"full_question_id": rec["full_question_id"],
                   "categories": rec["categories"], "gold": rec["answer"],
                   "pred": pred, "correct": correct, "seconds": round(time.time() - t0, 1)}
            if err:
                row["error"] = err
            out.write(json.dumps(row) + "\n")
            out.flush()

            mark = "✓" if correct else "✗"
            tag = (err and "ERR") or ",".join(c[:4] for c in rec["categories"][:2])
            print(f"[{board.total:4d}/{target}] {mark} gold={rec['answer']} "
                  f"pred={pred or '—'}  {board.line(target)}  :: {tag}")
            if board.total % every == 0:
                print(board.table())
    print("\nFINAL:")
    print(board.table())
    return board
