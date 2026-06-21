#!/usr/bin/env python3
"""Compute answer-agreement uncertainty over cases that already have greedy answers.

    python scripts/run_uncertainty.py --limit 120 --k 4

Then analyse the risk-coverage trade-off:
    python scripts/run_uncertainty.py --analyze
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radquant.eval.chestagentbench import RESULTS_DIR, load_records
from radquant.eval.uncertainty import run_uncertainty


def analyze(tag: str = "uncertainty") -> None:
    rows = [json.loads(l) for l in (RESULTS_DIR / f"run_{tag}.jsonl").open()]
    n = len(rows)
    overall = sum(r["correct"] for r in rows) / n
    print(f"\n{n} cases · overall accuracy {overall*100:.1f}%\n")
    print("SELECTIVE PREDICTION (answer only when sampled reasonings agree ≥ τ,")
    print("defer the rest to the radiologist):\n")
    print(f"  {'agreement τ':>12} {'coverage':>9} {'answered acc':>13} {'deferred':>9}")
    for tau in (0.0, 0.5, 0.75, 1.0):
        kept = [r for r in rows if r["agreement"] >= tau]
        if not kept:
            continue
        cov = len(kept) / n
        acc = sum(r["correct"] for r in kept) / len(kept)
        print(f"  {tau:>12.2f} {cov*100:7.0f}% {acc*100:12.1f}% {(1-cov)*100:8.0f}%")
    print("\nIf accuracy rises as coverage falls, the agreement signal is a valid")
    print("confidence measure — RadQuant can safely auto-handle the easy cases and")
    print("route the hard ones to a radiologist.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=120)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args()

    if args.analyze:
        analyze()
        return
    records = load_records(limit=args.limit, seed=args.seed)
    try:
        run_uncertainty(records, k=args.k)
    except KeyboardInterrupt:
        print("\n[interrupted] partial saved — re-run to resume, or --analyze.")
    analyze()


if __name__ == "__main__":
    main()
