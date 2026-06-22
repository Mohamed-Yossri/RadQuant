"""LangChain tools exposing RadQuant's CV stack to the interactive agent.

The orchestrator LLM (text-only) calls these to *see* the image: localize
findings as boxes (auditor) and segment anatomy + estimate the cardiothoracic
ratio (PSPNet). Paired with MedGemmaVQATool + the classifier, this is the full
tool suite for the "ask RadQuant about this case" assistant.
"""

from __future__ import annotations

from typing import Optional, Type

from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool


class _ImagePathInput(BaseModel):
    image_path: str = Field(..., description="Path to the chest X-ray (JPG/PNG).")


def _region(box) -> str:
    """Map a normalized [y0,x0,y1,x1] box to a CXR zone (patient laterality)."""
    y0, x0, y1, x1 = box
    cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
    vert = "upper" if cy < 0.40 else ("mid" if cy < 0.66 else "lower")
    # PA CXR is mirrored: image-left (small x) is the patient's right side.
    side = "right" if cx < 0.42 else ("left" if cx > 0.58 else "central")
    return f"{side} {vert} zone"


class LocalizeFindingsTool(BaseTool):
    """Bounding-box detection/localization of CXR findings (the auditor model)."""

    name: str = "localize_findings"
    description: str = (
        "Detect and LOCALIZE abnormal findings on a FRONTAL chest X-ray as labeled "
        "regions: pleural effusion, pneumothorax, lung opacity/consolidation, "
        "nodule/mass, cardiomegaly. Input: image_path. Output: each finding with the "
        "lung zone it occupies. Use this to answer 'where' questions."
    )
    args_schema: Type[BaseModel] = _ImagePathInput

    def _run(self, image_path: str, run_manager=None) -> str:
        from radquant.models.auditor import get_auditor, PRETTY
        try:
            f = get_auditor().detect(image_path)
        except Exception as e:  # noqa: BLE001
            return f"localization failed: {e}"
        if not f:
            return "No focal abnormal findings localized (image may be normal or non-frontal)."
        return "; ".join(f"{PRETTY.get(x['label'], x['label'])} in the {_region(x['box'])}"
                         for x in f)


class SegmentAnatomyTool(BaseTool):
    """Lung-field + heart segmentation with an approximate cardiothoracic ratio."""

    name: str = "segment_anatomy"
    description: str = (
        "Segment anatomy (lung fields, heart) on a FRONTAL chest X-ray and report an "
        "APPROXIMATE cardiothoracic ratio (CTR; >0.5 suggests cardiomegaly). Input: "
        "image_path. Use this for anatomy/size questions."
    )
    args_schema: Type[BaseModel] = _ImagePathInput

    def _run(self, image_path: str, run_manager=None) -> str:
        import numpy as np
        from radquant.models.segmenter import get_segmenter
        try:
            _disp, masks = get_segmenter().segment(image_path)
        except Exception as e:  # noqa: BLE001
            return f"segmentation failed: {e}"

        def width(m) -> int:
            cols = np.where(m.any(axis=0))[0]
            return int(cols.max() - cols.min()) if len(cols) else 0

        present = [k for k, v in masks.items() if v.mean() > 0.005]
        if not present:
            return "No clear anatomy segmented (image may be non-frontal)."
        thorax = masks["Left Lung"] | masks["Right Lung"]
        hw, tw = width(masks["Heart"]), width(thorax)
        ctr = hw / tw if tw else 0.0
        flag = " (enlarged — suggests cardiomegaly)" if ctr > 0.5 else " (normal)"
        return (f"Segmented: {', '.join(present)}. Approximate cardiothoracic ratio "
                f"{ctr:.2f}{flag if hw else ''}.")
