"""Grounded CXR finding detection (bounding boxes) — RadQuant's localization stage.

Wraps `alex-feeel/medgemma-cxr-auditor-v2`, a MedGemma-1.5-4B fine-tune that emits
constrained findings as JSON with normalized `[y0,x0,y1,x1]` boxes. We use the
author's *exact pinned grounding prompt* (the model is prompt-sensitive — a
different prompt yields 0–1000 coords and verbose output), a tolerant object-level
parser, and greedy IoU-NMS to dedupe overlapping boxes.

Attribution: model + prompt from the CXR Draft Auditor project
(https://huggingface.co/spaces/build-small-hackathon/cxr-draft-auditor), a
research derivative of google/medgemma-1.5-4b-it (HAI-DEF license, research-only).

IMPORTANT: trained on *frontal chest X-rays* (VinDr-CXR / ChestX-Det / NIH). It is
out-of-distribution on CT panels or annotated multi-image figures.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from pathlib import Path
from typing import List, Optional

import torch
from PIL import Image, ImageDraw

AUDITOR_REPO = "alex-feeel/medgemma-cxr-auditor-v2"
_LABELS = ("pleural_effusion, pneumothorax, lung_opacity_consolidation, "
           "nodule_mass, cardiomegaly, no_finding")

# Verbatim IMAGE_GROUNDING_PROMPT from cxr_auditor/prompts.py (label list filled).
GROUNDING_PROMPT = f"""\
You are a chest X-ray finding extractor for a research quality-assurance tool. This is NOT diagnosis and NOT clinical use.

Look at the chest X-ray and report ONLY findings drawn from this fixed label set:
{_LABELS}

Rules:
- Use ONLY the labels above, spelled exactly as written (lowercase, underscores).
- Return a JSON list. Each element is an object with these keys:
  - "label": one label from the set above.
  - "box_2d": [y0, x0, y1, x1], the bounding box normalized to [0, 1], where
    (y0, x0) is the top-left corner and (y1, x1) is the bottom-right corner.
    y is the vertical axis (top=0, bottom=1); x is the horizontal axis
    (left=0, right=1).
  - "confidence": a number in [0, 1].
  - "evidence": a short phrase describing the visual evidence.
- If a finding is genuinely present but not localizable to a box, set "box_2d" to null.
- If there is no abnormal finding, return a single element with "label": "no_finding".
- Output ONLY the JSON list. No prose, no markdown fences, no commentary.

Example output for an image with a left-sided pleural effusion:
[{{"label": "pleural_effusion", "box_2d": [0.62, 0.08, 0.94, 0.40], "confidence": 0.78, "evidence": "blunting and opacity at the left costophrenic angle"}}]

Example output for a normal image:
[{{"label": "no_finding", "box_2d": null, "confidence": 0.90, "evidence": "clear lung fields, normal cardiomediastinal silhouette"}}]
"""

PRETTY = {
    "pleural_effusion": "Pleural effusion", "pneumothorax": "Pneumothorax",
    "lung_opacity_consolidation": "Lung opacity / consolidation",
    "nodule_mass": "Nodule / mass", "cardiomegaly": "Cardiomegaly",
}

_INSTANCE = None
_LOCK = threading.Lock()


class Auditor:
    """The grounding model: image → list of {label, box, confidence}."""

    def __init__(self, device: str = "cuda"):
        from transformers import AutoModelForImageTextToText, AutoProcessor

        # Free any reclaimable VRAM before pulling in this second ~8 GB model —
        # on a busy 24 GB card the first load is where OOM bites.
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass

        self.processor = AutoProcessor.from_pretrained(AUDITOR_REPO)
        self.model = AutoModelForImageTextToText.from_pretrained(
            AUDITOR_REPO, dtype=torch.bfloat16, device_map=device,
            attn_implementation="sdpa",
        ).eval()

    @torch.inference_mode()
    def _raw(self, image: Image.Image, max_new_tokens: int = 384) -> str:
        msgs = [{"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": GROUNDING_PROMPT}]}]
        inp = self.processor.apply_chat_template(
            msgs, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt").to(self.model.device)
        n = inp["input_ids"].shape[-1]
        gen = self.model.generate(**inp, max_new_tokens=max_new_tokens, do_sample=False)
        return self.processor.decode(gen[0][n:], skip_special_tokens=True).strip()

    def detect(self, image_path: str, iou_thresh: float = 0.5,
               max_findings: int = 6) -> List[dict]:
        """Return deduped findings: [{label, box:[y0,x0,y1,x1], confidence}]."""
        raw = self._raw(Image.open(image_path).convert("RGB"))
        items = _parse(raw)
        items.sort(key=lambda d: d.get("confidence", 0.0), reverse=True)
        return _nms(items, iou_thresh)[:max_findings]


def get_auditor() -> "Auditor":
    global _INSTANCE
    if _INSTANCE is None:
        with _LOCK:
            if _INSTANCE is None:
                _INSTANCE = Auditor()
    return _INSTANCE


# --------------------------------------------------------------------------- #
def _parse(text: str) -> List[dict]:
    """Tolerant object-level parse; drop no_finding / null boxes; coords -> [0,1]."""
    out = []
    for m in re.finditer(r'\{[^{}]*?"label"\s*:\s*"([a-z_]+)"[^{}]*?\}', text, re.S):
        try:
            it = json.loads(m.group(0))
        except Exception:
            continue
        box = it.get("box_2d")
        if it.get("label") in (None, "no_finding") or not box or len(box) != 4:
            continue
        box = [float(v) for v in box]
        if max(box) > 1.5:           # guard: some prompts elicit 0–1000
            box = [v / 1000.0 for v in box]
        box = [min(1.0, max(0.0, v)) for v in box]
        out.append({"label": it["label"], "box": box,
                    "confidence": float(it.get("confidence", 0.5))})
    return out


def _iou(a: list, b: list) -> float:
    ay0, ax0, ay1, ax1 = a; by0, bx0, by1, bx1 = b
    iy0, ix0 = max(ay0, by0), max(ax0, bx0)
    iy1, ix1 = min(ay1, by1), min(ax1, bx1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    ua = (ay1 - ay0) * (ax1 - ax0) + (by1 - by0) * (bx1 - bx0) - inter
    return inter / ua if ua > 0 else 0.0


def _nms(items: List[dict], thresh: float) -> List[dict]:
    """Greedy NMS: suppress same-label boxes overlapping a kept higher-conf box."""
    kept: List[dict] = []
    for it in items:
        if any(k["label"] == it["label"] and _iou(k["box"], it["box"]) > thresh
               for k in kept):
            continue
        kept.append(it)
    return kept


_COLORS = {"pleural_effusion": "#22D3EE", "pneumothorax": "#F87171",
           "lung_opacity_consolidation": "#FBBF24", "nodule_mass": "#A78BFA",
           "cardiomegaly": "#34D399"}


def render_overlay(image_path: str, findings: List[dict],
                   out_dir: str | Path = "temp/grounding") -> str:
    """Draw labeled boxes on the image; return the overlay PNG path."""
    im = Image.open(image_path).convert("RGB")
    W, H = im.size
    d = ImageDraw.Draw(im)
    for f in findings:
        y0, x0, y1, x1 = f["box"]
        color = _COLORS.get(f["label"], "#FF0000")
        d.rectangle([x0 * W, y0 * H, x1 * W, y1 * H], outline=color, width=max(2, W // 200))
        d.text((x0 * W + 4, y0 * H + 4),
               f"{PRETTY.get(f['label'], f['label'])} {f['confidence']:.2f}", fill=color)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"ground_{uuid.uuid4().hex[:8]}.png"
    im.save(out)
    return str(out)
