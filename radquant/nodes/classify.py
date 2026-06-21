"""`classify` node — 18-class chest X-ray pathology probabilities.

Wraps the foundation TorchXRayVision classifier behind a process-wide singleton
(the DenseNet is small, but reloading per case is wasteful) and adapts it to the
LangGraph CaseState contract.
"""

from __future__ import annotations

import math
import threading
from typing import Dict, Optional

from radquant.foundation import ChestXRayClassifierTool

_CLF: Optional[ChestXRayClassifierTool] = None
_LOCK = threading.Lock()


def get_classifier(device: str = "cuda") -> ChestXRayClassifierTool:
    """Return the process-wide classifier singleton."""
    global _CLF
    if _CLF is None:
        with _LOCK:
            if _CLF is None:
                _CLF = ChestXRayClassifierTool(device=device)
    return _CLF


def classify_image(image_path: str, device: str = "cuda") -> Dict[str, float]:
    """Return ``{pathology: probability}`` for all 18 classes (NaNs -> 0.0)."""
    preds, meta = get_classifier(device)._run(image_path)
    if "error" in preds:
        raise RuntimeError(f"classification failed: {preds['error']}")
    return {k: (0.0 if (v is None or math.isnan(v)) else float(v)) for k, v in preds.items()}


def classify(state: dict) -> dict:
    """LangGraph node: read ``state['image_path']`` → write ``state['findings']``."""
    findings = classify_image(state["image_path"])
    return {"findings": findings}
