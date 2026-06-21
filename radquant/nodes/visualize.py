"""`visualize` node — Grad-CAM heatmap over the classifier's top-1 finding.

Produces an overlay PNG showing where the DenseNet attended when predicting the
single most likely pathology, so a radiologist can sanity-check the classifier's
spatial focus.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np

from radquant.nodes.classify import get_classifier

DEFAULT_HEATMAP_DIR = Path("temp") / "heatmaps"


def gradcam_overlay(
    image_path: str,
    finding: Optional[str] = None,
    findings: Optional[Dict[str, float]] = None,
    out_dir: Path | str = DEFAULT_HEATMAP_DIR,
) -> Tuple[str, str]:
    """Render a Grad-CAM overlay for ``finding`` (or the top-1 finding).

    Returns (overlay_png_path, finding_name).
    """
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
    from pytorch_grad_cam.utils.image import show_cam_on_image
    from PIL import Image

    tool = get_classifier()
    model = tool.model

    # Choose the target pathology.
    if finding is None:
        if findings:
            finding = max(findings, key=findings.get)
        else:
            preds, _ = tool._run(image_path)
            finding = max(preds, key=preds.get)
    target_idx = list(model.pathologies).index(finding)

    # Model input tensor (xrv-normalized, on the model's device).
    inp = tool._process_image(image_path)  # (1, 1, H, W)

    # Grayscale base image in [0, 1], 3-channel, matching the input spatial size.
    base = inp[0, 0].detach().float().cpu().numpy()
    base = (base - base.min()) / (base.max() - base.min() + 1e-8)
    rgb = np.stack([base] * 3, axis=-1)

    cam = GradCAM(model=model, target_layers=[model.features.norm5])
    grayscale_cam = cam(input_tensor=inp, targets=[ClassifierOutputTarget(target_idx)])[0]
    overlay = show_cam_on_image(rgb, grayscale_cam, use_rgb=True)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"gradcam_{finding.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.png"
    Image.fromarray(overlay).save(out_path)
    return str(out_path), finding


def visualize(state: dict) -> dict:
    """LangGraph node: image + findings → heatmap_path (Grad-CAM on top-1)."""
    path, _finding = gradcam_overlay(state["image_path"], findings=state.get("findings"))
    return {"heatmap_path": path}
