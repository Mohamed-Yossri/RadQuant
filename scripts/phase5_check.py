#!/usr/bin/env python3
"""Phase 5 done-when: omission QC with the real MedGemma judge.

Three PLAN.md cases:
  (a) pneumothorax 0.8, report omits it            -> flagged
  (b) pneumothorax 0.8, report says "no pneumothorax" -> NOT flagged
  (c) effusion 0.8, report says "blunting of the right costophrenic angle"
                                                   -> NOT flagged (synonym)

Run: python scripts/phase5_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radquant.nodes.qc import find_omissions


def show(label: str, oms: list) -> None:
    flagged = [o["finding"] for o in oms]
    print(f"\n[{label}] omissions: {flagged or 'none'}")
    for o in oms:
        print(f"    - {o['finding']} ({o['confidence']}) via {o['method']}")


def main() -> None:
    # (a) unmentioned -> flagged (this one actually consults MedGemma)
    a = find_omissions("The lungs are clear. The heart size is normal.",
                       {"Pneumothorax": 0.8})
    show("a) omitted pneumothorax", a)
    assert [o["finding"] for o in a] == ["Pneumothorax"], "should flag pneumothorax"

    # (b) explicitly ruled out -> not flagged (lexical short-circuit)
    b = find_omissions("The lungs are clear. No pneumothorax.", {"Pneumothorax": 0.8})
    show("b) 'no pneumothorax'", b)
    assert b == [], "explicit negation should not be an omission"

    # (c) synonym phrasing -> not flagged (lexical short-circuit)
    c = find_omissions("There is blunting of the right costophrenic angle.",
                       {"Effusion": 0.8})
    show("c) costophrenic blunting (= effusion)", c)
    assert c == [], "synonym should not be an omission"

    print("\n\033[32m✓ Phase 5 check passed — omission QC flags (a), clears (b) and (c).\033[0m")


if __name__ == "__main__":
    main()
