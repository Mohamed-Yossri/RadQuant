"""Sample-image helper.

Per PLAN.md, test/dev code should call ``radcopilot.data.sample(n, ...)`` rather
than hardcoding paths. Images come from the ChestAgentBench ``figures`` bundle
downloaded by ``scripts/setup.py``.
"""

from __future__ import annotations

import random
from pathlib import Path

from radcopilot.config import DATA_DIR

CHESTAGENTBENCH_DIR = DATA_DIR / "chestagentbench"
_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def _all_figures() -> list[Path]:
    if not CHESTAGENTBENCH_DIR.exists():
        return []
    return sorted(
        p for p in CHESTAGENTBENCH_DIR.rglob("*") if p.suffix.lower() in _IMAGE_EXTS
    )


def sample(n: int = 1, pathology: str | None = None, modality: str = "cxr",
           seed: int | None = 0) -> list[Path]:
    """Return ``n`` sample image paths from the ChestAgentBench figures.

    Args:
        n: number of images to return.
        pathology: not yet supported (figures lack per-image pathology labels);
            passing it logs no error but currently does not filter. Phase 3+ may
            wire this through the benchmark metadata. Reserved for forward-compat.
        modality: reserved; only "cxr" is available in v1.
        seed: deterministic selection by default; pass ``None`` for random.

    Raises:
        FileNotFoundError: if the figures bundle has not been downloaded yet.
    """
    figures = _all_figures()
    if not figures:
        raise FileNotFoundError(
            f"No ChestAgentBench figures found under {CHESTAGENTBENCH_DIR}. "
            "Run `python scripts/setup.py` first."
        )
    if n >= len(figures):
        return figures
    if seed is None:
        return random.sample(figures, n)
    return random.Random(seed).sample(figures, n)
