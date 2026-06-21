"""Shared LangGraph state. See PLAN.md "Architecture".

All nodes read from and write to a single ``CaseState`` dict. Fields are
populated progressively as a case moves through the graph:

    ingest -> classify -> triage -> visualize -> draft -> review -> qc -> END

``explain`` is a side-call available from any state that has report text.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np


class CaseState(TypedDict, total=False):
    case_id: str
    image_path: str            # DICOM or PNG/JPG on disk
    image_array: np.ndarray    # preprocessed image tensor (H, W) or (H, W, C)
    dicom_metadata: dict       # extracted DICOM tags (empty for non-DICOM)
    findings: dict             # {pathology_name: probability}
    urgency_score: float       # weighted triage score
    heatmap_path: str          # Grad-CAM overlay on disk
    draft_findings: str        # MedGemma-generated FINDINGS section
    draft_impression: str      # MedGemma-generated IMPRESSION section
    omissions: list            # [{finding, confidence, suggestion}]
    radiologist_edits: dict    # UI-captured edits
    final_report: str          # radiologist-approved report text
    explainer_output: str      # plain-language patient version
    action: str                # review router control: "regenerate" | "finalize"
