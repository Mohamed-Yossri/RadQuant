#!/usr/bin/env python3
"""Fetch a small set of real frontal chest X-rays for the demo + grounding.

The ChestAgentBench figures are mostly CT panels / annotated multi-image figures —
out-of-distribution for the classifier and the grounding model. The grounding
(bounding-box) feature only works on plain frontal CXRs, so we fetch a handful:

  - a few pneumonia / normal frontal CXRs (hf-vision/chest-xray-pneumonia)
  - the auditor author's 4 curated example CXRs (known-good grounding inputs)

Run: python scripts/fetch_demo_cxr.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUT = Path("data/demo_cxr")
AUTHOR = OUT / "author"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    AUTHOR.mkdir(parents=True, exist_ok=True)

    # 1) pneumonia + normal frontal CXRs (streamed, a handful)
    try:
        from datasets import load_dataset
        ds = load_dataset("hf-vision/chest-xray-pneumonia", split="test", streaming=True)
        n = {0: 0, 1: 0}
        for r in ds:
            lab = int(r["label"])
            cap = 6 if lab == 1 else 3
            if n[lab] < cap:
                name = "pneumonia" if lab == 1 else "normal"
                r["image"].convert("RGB").save(OUT / f"{name}_{n[lab]}.png")
                n[lab] += 1
            if n[0] >= 3 and n[1] >= 6:
                break
        print(f"✓ saved {n[1]} pneumonia + {n[0]} normal frontal CXRs -> {OUT}")
    except Exception as e:  # noqa: BLE001
        print(f"! pneumonia CXR fetch failed ({e})")

    # 2) auditor author's curated example CXRs (known-good grounding inputs)
    try:
        from huggingface_hub import hf_hub_download
        for i in (1, 2, 3, 4):
            p = hf_hub_download("build-small-hackathon/cxr-draft-auditor",
                                f"examples/cxr_example_{i}.png", repo_type="space")
            shutil.copy(p, AUTHOR / f"example_{i}.png")
        print(f"✓ saved 4 curated example CXRs -> {AUTHOR}")
    except Exception as e:  # noqa: BLE001
        print(f"! example CXR fetch failed ({e})")


if __name__ == "__main__":
    main()
