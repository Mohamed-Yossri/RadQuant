"""MedSAM — universal medical-image segmentation (box-prompted, any modality).

MedSAM (Ma et al., *Nature Communications* 2024) is the Segment Anything Model
fine-tuned on 1.5M medical image–mask pairs across 10 modalities. Given a
bounding box, it segments the structure inside it — on CT, MRI, X-ray,
ultrasound, etc. Unlike the CXR-only PSPNet segmenter (lung/heart on chest
radiographs), MedSAM generalises across radiology and beyond.

We use the transformers-native port (``flaviagiammarino/medsam-vit-base``,
`SamModel`/`SamProcessor`) — no detectron2 / custom repo, so it can't disturb
the pinned torch/CUDA stack. ViT-B is light (~0.37 GB VRAM) and loads lazily as
a process-wide singleton.
"""

from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

_REPO = "flaviagiammarino/medsam-vit-base"
_MODEL = None
_PROC = None
_LOCK = threading.Lock()

DEFAULT_DIR = Path("temp") / "medsam"


def _device() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


def get_medsam():
    """Return the process-wide (model, processor) singleton."""
    global _MODEL, _PROC
    if _MODEL is None:
        with _LOCK:
            if _MODEL is None:
                from transformers import SamModel, SamProcessor
                dev = _device()
                _MODEL = SamModel.from_pretrained(_REPO).to(dev).eval()
                _PROC = SamProcessor.from_pretrained(_REPO)
    return _MODEL, _PROC


def segment_box(image_path: str, box: List[float]) -> np.ndarray:
    """Boolean HxW mask for the structure inside ``box`` = [x0,y0,x1,y1] (px)."""
    import torch
    from PIL import Image

    model, proc = get_medsam()
    img = Image.open(image_path).convert("RGB")
    coords = [[float(b) for b in box]]
    inputs = proc(img, input_boxes=[coords], return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model(**inputs, multimask_output=False)
    masks = proc.image_processor.post_process_masks(
        out.pred_masks.cpu(),
        inputs["original_sizes"].cpu(),
        inputs["reshaped_input_sizes"].cpu(),
    )
    return masks[0][0][0].numpy().astype(bool)


def _recist(mask: np.ndarray):
    """RECIST-style longest diameter + perpendicular short axis (in pixels).

    Longest diameter = max caliper (Feret) distance across the lesion — the
    standard target-lesion measurement. Short axis = extent perpendicular to it.
    Returns (longest_px, short_px, (p1, p2)) with p1/p2 the diameter endpoints.
    """
    ys, xs = np.where(mask)
    if len(xs) < 2:
        return 0.0, 0.0, None
    pts = np.column_stack([xs, ys]).astype(float)
    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(pts)
        hp = pts[hull.vertices]
    except Exception:  # noqa: BLE001  (degenerate/collinear)
        hp = pts
    from scipy.spatial.distance import cdist
    D = cdist(hp, hp)
    i, j = np.unravel_index(int(np.argmax(D)), D.shape)
    p1, p2 = hp[i], hp[j]
    longest = float(D[i, j])
    axis = (p2 - p1) / (longest + 1e-9)
    perp = np.array([-axis[1], axis[0]])
    proj = hp @ perp
    short = float(proj.max() - proj.min())
    return longest, short, (p1, p2)


def segment_overlay(image_path: str, box: List[float],
                    out_dir: str | Path = DEFAULT_DIR) -> Tuple[str, Dict]:
    """Segment, render mask + prompt box + RECIST caliper line, return (path, stats)."""
    from PIL import Image, ImageDraw

    mask = segment_box(image_path, box)
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    lw = max(2, img.size[0] // 400)

    teal = np.array([45, 212, 191], dtype=np.float32)
    blended = arr.copy()
    if mask.any():
        blended[mask] = (0.45 * teal + 0.55 * arr[mask].astype(np.float32)).astype(np.uint8)
    out_img = Image.fromarray(blended)
    draw = ImageDraw.Draw(out_img)
    draw.rectangle([float(box[0]), float(box[1]), float(box[2]), float(box[3])],
                   outline=(56, 189, 248), width=lw)

    ys, xs = np.where(mask)
    w_px = int(xs.max() - xs.min()) + 1 if len(xs) else 0
    h_px = int(ys.max() - ys.min()) + 1 if len(ys) else 0
    area = int(mask.sum())

    longest_px, short_px, endpoints = _recist(mask)
    if endpoints is not None:
        (x1, y1), (x2, y2) = endpoints
        draw.line([(x1, y1), (x2, y2)], fill=(244, 211, 94), width=lw)  # caliper
        r = lw * 2
        for (cx, cy) in ((x1, y1), (x2, y2)):
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(244, 211, 94))

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"medsam_{uuid.uuid4().hex[:8]}.png"
    out_img.save(out)

    stats = {
        "area_px": area,
        "area_pct": round(mask.mean() * 100, 1) if mask.size else 0.0,
        "width_px": w_px,
        "height_px": h_px,
        "longest_diameter_px": round(longest_px, 1),
        "short_axis_px": round(short_px, 1),
        "image_w": img.size[0],
        "image_h": img.size[1],
    }
    return str(out), stats
