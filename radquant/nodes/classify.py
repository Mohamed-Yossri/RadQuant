"""`classify` node — 18-class chest X-ray pathology probabilities.

Wraps the foundation TorchXRayVision classifier behind a process-wide singleton
(the DenseNet is small, but reloading per case is wasteful) and adapts it to the
LangGraph CaseState contract.
"""

from __future__ import annotations

import logging
import math
import threading
from typing import Dict, Optional

from radquant.foundation import ChestXRayClassifierTool

logger = logging.getLogger(__name__)

_CLF: Optional[ChestXRayClassifierTool] = None
_LOCK = threading.Lock()


def _auto_device() -> str:
    """Pick the best available device."""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


def get_classifier(device: str | None = None) -> ChestXRayClassifierTool:
    """Return the process-wide classifier singleton."""
    global _CLF
    if _CLF is None:
        with _LOCK:
            if _CLF is None:
                dev = device or _auto_device()
                logger.info("Initializing classifier on device=%s", dev)
                _CLF = ChestXRayClassifierTool(device=dev)
    return _CLF


def classify_image(image_path: str, device: str | None = None) -> Dict[str, float]:
    """Return ``{pathology: probability}`` for all 18 classes (NaNs -> 0.0).

    Gracefully handles model loading failures by returning an error dict.
    """
    try:
        preds, meta = get_classifier(device)._run(image_path)
    except Exception as e:
        logger.error("Classifier failed to load or run: %s", e)
        raise RuntimeError(
            f"Classification failed: {e}. "
            "Ensure torch and torchxrayvision are installed."
        ) from e

    if "error" in preds:
        raise RuntimeError(f"classification failed: {preds['error']}")
    return {k: (0.0 if (v is None or math.isnan(v)) else float(v)) for k, v in preds.items()}


def classify(state: dict) -> dict:
    """LangGraph node: read ``state['image_path']`` → write ``state['findings']``."""
    findings = classify_image(state["image_path"])
    return {"findings": findings}
