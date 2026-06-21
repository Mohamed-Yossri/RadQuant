#!/usr/bin/env python3
"""Benchmark MedGemma 1.5 4B: tokens/sec and peak VRAM over 5 inferences.

Run: python scripts/bench_medgemma.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import torch  # noqa: E402
from PIL import Image  # noqa: E402

from radquant.data import sample  # noqa: E402
from radquant.models import get_medgemma  # noqa: E402


def main() -> None:
    img = Image.open(sample(1)[0]).convert("RGB")
    prompts = [
        "Describe the findings in this chest X-ray.",
        "Is there any evidence of pleural effusion? Explain.",
        "Summarize this X-ray in one impression line.",
        "List the anatomical structures visible.",
        "What is the overall image quality?",
    ]

    mg = get_medgemma()
    print(f"quant={mg.quant} | load={mg.load_seconds:.1f}s")

    torch.cuda.reset_peak_memory_stats()
    # Warm-up (first call has CUDA graph / kernel autotune overhead).
    _ = mg.generate(img, "Hi.", max_new_tokens=8)

    total_tokens, total_time = 0, 0.0
    enc = mg.processor.tokenizer
    for i, p in enumerate(prompts):
        t0 = time.time()
        out = mg.generate(img, p, max_new_tokens=128)
        dt = time.time() - t0
        n = len(enc(out)["input_ids"])
        total_tokens += n
        total_time += dt
        print(f"  [{i+1}] {n:3d} tok in {dt:4.1f}s "
              f"({n/dt:5.1f} tok/s) :: {out[:60]!r}")

    peak = torch.cuda.max_memory_allocated() / 1e9
    print(f"\n  AVG: {total_tokens/total_time:.1f} tok/s over {len(prompts)} calls")
    print(f"  PEAK VRAM: {peak:.1f} GB / 23 GB (L4)")
    print("  (MedGemma 1.5 4B on L4 bf16 — small-batch decode is bandwidth-bound; "
          "single-digit-to-low-tens tok/s is expected.)")


if __name__ == "__main__":
    main()
