#!/usr/bin/env python3
"""Run the ChestAgentBench evaluation with a live, resumable scoreboard.

Calibration first (recommended): a small stratified batch to read accuracy early.
    python scripts/run_eval.py --limit 30 --stratified

Full run (resumable — re-run to continue; Ctrl-C anytime):
    python scripts/run_eval.py --full

Results stream to data/eval_results/run_<backend>.jsonl.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radquant.eval.chestagentbench import load_records, run


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=30, help="number of questions")
    ap.add_argument("--full", action="store_true", help="run all 2500 (overrides --limit)")
    ap.add_argument("--stratified", action="store_true",
                    help="balance the sample across the 7 categories")
    ap.add_argument("--backend", default="nvidia", choices=["nvidia", "groq"])
    ap.add_argument("--seed", type=int, default=0)
    # direct multi-image VLM mode (Experiment 1+) and its ablations
    ap.add_argument("--direct", action="store_true",
                    help="MedGemma answers the MCQ directly (multi-image), no agent")
    ap.add_argument("--agentic", action="store_true",
                    help="MedGemma perceive->decide agent with self-rated confidence")
    ap.add_argument("--tag", default=None, help="results filename tag (direct mode)")
    ap.add_argument("--no-cot", action="store_true", help="disable chain-of-thought")
    ap.add_argument("--answer-first", action="store_true",
                    help="emit 'Answer: X' first, then justify (guarantees a parse)")
    ap.add_argument("--classifier", action="store_true", help="append a classifier hint")
    ap.add_argument("--pan-scan", action="store_true",
                    help="enable pan-and-scan high-res image tiling")
    ap.add_argument("--k", type=int, default=1, help="self-consistency samples (majority vote)")
    args = ap.parse_args()

    limit = None if args.full else args.limit
    records = load_records(limit=limit, stratified=args.stratified, seed=args.seed)
    mode = "FULL" if args.full else f"limit={args.limit}, stratified={args.stratified}"

    try:
        if args.agentic:
            from radquant.eval.agentic import run_agentic
            tag = args.tag or "agentic"
            print(f"ChestAgentBench AGENTIC — {mode}, {len(records)} questions\n")
            run_agentic(records, tag=tag, classifier_hint=args.classifier)
        elif args.direct:
            from radquant.eval.direct import run_direct
            tag = args.tag or ("direct" if not args.classifier else "direct_clf")
            print(f"ChestAgentBench DIRECT — {mode}, {len(records)} questions\n")
            run_direct(records, tag=tag, cot=not args.no_cot,
                       with_classifier=args.classifier,
                       answer_first=args.answer_first, k=args.k,
                       pan_and_scan=args.pan_scan)
        else:
            print(f"ChestAgentBench AGENT — {mode}, {len(records)} q, backend={args.backend}\n")
            run(records, backend=args.backend)
    except KeyboardInterrupt:
        print("\n\n[interrupted] partial results saved — re-run to resume.")


if __name__ == "__main__":
    main()
