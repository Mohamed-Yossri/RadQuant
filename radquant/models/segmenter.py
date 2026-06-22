"""Anatomical segmentation for CXR — RadQuant's structure-overlay stage.

Wraps TorchXRayVision's ChestX-Det **PSPNet** (the same segmentation model MedRAX
used) to outline lung fields and the heart. No extra dependency — torchxrayvision
is already installed; the weights (~tens of MB) auto-download on first use.

Produces a translucent color overlay (left lung / right lung / heart) aligned to
the 512×512 center-cropped image the model sees.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
from PIL import Image

# structure -> RGB colour (cyan lungs, green lung, red heart)
STRUCTURES: Dict[str, Tuple[int, int, int]] = {
    "Left Lung": (34, 211, 238),
    "Right Lung": (52, 211, 153),
    "Heart": (248, 113, 113),
}

_INSTANCE = None
_LOCK = threading.Lock()


class Segmenter:
    def __init__(self, device: str = "cuda"):
        import torchvision
        import torchxrayvision as xrv

        self.model = xrv.baseline_models.chestx_det.PSPNet().eval().to(device)
        self.device = device
        self.targets = list(self.model.targets)
        self.transform = torchvision.transforms.Compose(
            [xrv.datasets.XRayCenterCrop(), xrv.datasets.XRayResizer(512)]
        )

    @torch.inference_mode()
    def segment(self, image_path: str, thresh: float = 0.5):
        """Return (display_image[0..1] HxW, {structure: bool mask})."""
        import skimage.io
        import torchxrayvision as xrv

        img = skimage.io.imread(image_path)
        img = xrv.datasets.normalize(img, 255)
        if img.ndim > 2:
            img = img[:, :, 0]
        img = self.transform(img[None, ...])  # (1, 512, 512)
        x = torch.from_numpy(img)[None, ...].to(self.device)
        pred = torch.sigmoid(self.model(x))[0].cpu().numpy()  # (14, 512, 512)

        disp = img[0]
        disp = (disp - disp.min()) / (disp.max() - disp.min() + 1e-8)
        masks = {name: pred[self.targets.index(name)] > thresh for name in STRUCTURES}
        return disp, masks


def get_segmenter() -> "Segmenter":
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = Segmenter()
    return _INSTANCE


def segment_overlay(image_path: str, alpha: float = 0.35,
                    out_dir: str | Path = "temp/seg") -> Tuple[str, List[str]]:
    """Render translucent lung/heart masks over the CXR. Returns (png_path, present)."""
    disp, masks = get_segmenter().segment(image_path)
    rgb = np.stack([disp] * 3, axis=-1).astype(np.float32)  # (H, W, 3) in [0,1]
    present: List[str] = []
    for name, (r, g, b) in STRUCTURES.items():
        m = masks[name]
        if m.mean() < 0.005:  # not meaningfully present (e.g. non-frontal image)
            continue
        present.append(name)
        color = np.array([r, g, b], dtype=np.float32) / 255.0
        rgb[m] = (1 - alpha) * rgb[m] + alpha * color
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"seg_{uuid.uuid4().hex[:8]}.png"
    Image.fromarray((rgb * 255).astype(np.uint8)).save(out)
    return str(out), present
