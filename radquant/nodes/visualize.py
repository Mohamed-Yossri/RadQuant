"""
radquant/nodes/visualize.py — Grad-CAM heatmap overlay on classifier top-1 finding.
Target layer: features.norm5  (verified on DenseNet-121 torchxrayvision build).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

HEATMAP_DIR = Path("data/heatmaps")


def visualize_node(state: dict) -> dict:
    """
    LangGraph node: generate Grad-CAM heatmap for the top classifier finding.
    Saves overlay PNG to data/heatmaps/<case_id>.png.
    Populates state['heatmap_path'].
    """
    import torch
    import torchxrayvision as xrv
    from PIL import Image
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.image import show_cam_on_image
    from radquant.nodes.classify import _get_classifier

    findings = state.get("findings") or {}
    image_path = state.get("image_path")
    case_id = state.get("case_id", "unknown")

    if not findings or not image_path:
        logger.warning("visualize_node: nothing to visualize")
        return state

    # top finding
    top_pathology, top_prob = max(findings.items(), key=lambda x: x[1])
    logger.info("visualize_node: Grad-CAM for %s (%.2f)", top_pathology, top_prob)

    try:
        model = _get_classifier()

        # preprocess
        img_pil = Image.open(image_path).convert("L")
        img_np = np.array(img_pil).astype(np.float32)
        img_np = img_np / 255.0 * 2048 - 1024
        img_np = xrv.datasets.normalize(img_np, maxval=1024, reshape=True)
        tensor = torch.from_numpy(img_np).unsqueeze(0)

        target_layer = model.features.norm5

        # find class index
        pathologies = [p for p in model.pathologies if p]
        try:
            class_idx = pathologies.index(top_pathology)
        except ValueError:
            class_idx = 0

        from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
        targets = [ClassifierOutputTarget(class_idx)]

        with GradCAM(model=model, target_layers=[target_layer]) as cam:
            grayscale_cam = cam(input_tensor=tensor, targets=targets)[0]

        # build overlay
        img_rgb = Image.open(image_path).convert("RGB").resize((224, 224))
        img_float = np.array(img_rgb).astype(np.float32) / 255.0
        overlay = show_cam_on_image(img_float, grayscale_cam, use_rgb=True)

        HEATMAP_DIR.mkdir(parents=True, exist_ok=True)
        out_path = HEATMAP_DIR / f"{case_id}.png"
        Image.fromarray(overlay).save(out_path)

        logger.info("visualize_node: saved heatmap to %s", out_path)
        return {**state, "heatmap_path": str(out_path)}

    except Exception as exc:
        logger.error("visualize_node: failed — %s", exc)
        return state
