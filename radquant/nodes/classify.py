"""
radquant/nodes/classify.py — 18-pathology chest X-ray classifier.
Uses TorchXRayVision DenseNet-121 pretrained on multiple datasets.
"""

from __future__ import annotations

import logging
import threading

import numpy as np

logger = logging.getLogger(__name__)

_clf_lock = threading.Lock()
_clf_model = None


def _get_classifier():
    global _clf_model
    if _clf_model is None:
        with _clf_lock:
            if _clf_model is None:
                import torchxrayvision as xrv
                logger.info("classify: loading DenseNet-121 …")
                _clf_model = xrv.models.DenseNet(weights="densenet121-res224-all")
                _clf_model.eval()
                logger.info("classify: model ready (%d pathologies)", len(_clf_model.pathologies))
    return _clf_model


def classify_node(state: dict) -> dict:
    """
    LangGraph node: run TorchXRayVision classifier on state['image_path'].
    Populates state['findings'] = {pathology: probability}.
    """
    import torch
    import torchxrayvision as xrv
    from PIL import Image

    image_path = state.get("image_path")
    if not image_path:
        logger.error("classify_node: image_path missing")
        return state

    try:
        img = Image.open(image_path).convert("L")  # grayscale
        img_np = np.array(img).astype(np.float32)
        # Normalize to [-1024, 1024] as expected by torchxrayvision
        img_np = img_np / 255.0 * 2048 - 1024
        img_np = xrv.datasets.normalize(img_np, maxval=1024, reshape=True)

        model = _get_classifier()
        with torch.inference_mode():
            output = model(torch.from_numpy(img_np).unsqueeze(0))

        probs = output[0].detach().numpy()
        findings = {
            path: float(np.clip(p, 0, 1))
            for path, p in zip(model.pathologies, probs)
            if path  # skip empty pathology names
        }
        logger.info(
            "classify_node: top findings: %s",
            sorted(findings.items(), key=lambda x: -x[1])[:3],
        )
        return {**state, "findings": findings}

    except Exception as exc:
        logger.error("classify_node: failed — %s", exc)
        return {**state, "findings": {}}
