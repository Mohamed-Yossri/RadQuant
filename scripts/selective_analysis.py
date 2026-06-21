#!/usr/bin/env python3
"""Selective-prediction analysis — the "Quant" in RadQuant.

Given an eval results file that carries a per-case `confidence` (High/Medium/Low),
compute the risk–coverage trade-off: if RadQuant only answers when confident and
defers the rest to the radiologist, how accurate is it on what it DOES answer?

A safe system that knows when to abstain is clinically better than one that is
confidently wrong. Usage:

    python scripts/selective_analysis.py data/eval_results/run_agentic.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ORDER = {"High": 3, "Medium": 2, "Low": 1}


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1
                else "data/eval_results/run_agentic.jsonl")
    rows = [json.loads(l) for l in path.open() if l.strip()]
    n = len(rows)
    overall = sum(r["correct"] for r in rows) / n

    print(f"\n{path.name}: {n} cases, overall accuracy {overall*100:.1f}%\n")
    print("Selective prediction — answer only at/above a confidence level,")
    print("defer the rest to the radiologist:\n")
    print(f"  {'policy':24} {'coverage':>9} {'answered acc':>13} {'deferred':>9}")

    for label, floor in [("answer ALL", 1), ("conf >= Medium", 2), ("conf = High only", 3)]:
        kept = [r for r in rows if ORDER.get(r.get("confidence", "Medium"), 2) >= floor]
        if not kept:
            continue
        cov = len(kept) / n
        acc = sum(r["correct"] for r in kept) / len(kept)
        print(f"  {label:24} {cov*100:7.0f}% {acc*100:12.1f}% {(1-cov)*100:8.0f}%")

    # Confidence calibration sanity: accuracy should rise with confidence.
    print("\nCalibration (accuracy by self-rated confidence):")
    for c in ("High", "Medium", "Low"):
        sub = [r for r in rows if r.get("confidence") == c]
        if sub:
            print(f"  {c:7} {sum(r['correct'] for r in sub)/len(sub)*100:5.1f}%  (n={len(sub)})")

    print("\nPitch: RadQuant answers the cases it is sure about at high accuracy and "
          "routes the uncertain ones to a radiologist — selective, safe automation.")


if __name__ == "__main__":
    main()
