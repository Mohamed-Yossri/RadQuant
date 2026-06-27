"""
radquant/state.py — shared LangGraph state (TypedDict) for a single case.
Includes longitudinal comparison fields (Phase 10).
"""

from __future__ import annotations
from typing import TypedDict


class IntervalFinding(TypedDict):
    finding: str   # e.g. "right pleural effusion"
    change: str    # "new" | "worsened" | "improved" | "resolved" | "stable"
    detail: str    # free-text elaboration from MedGemma


class CaseState(TypedDict, total=False):
    # ── core fields ──────────────────────────────────────────────────────────
    case_id: str
    image_path: str
    image_array: object          # np.ndarray — typed as object to avoid numpy import
    dicom_metadata: dict
    findings: dict               # {pathology_name: probability}
    urgency_score: float
    urgency_tier: str            # "Critical" | "Urgent" | "Important" | "Chronic"
    heatmap_path: str
    draft_findings: str
    draft_impression: str
    omissions: list              # list[dict]
    radiologist_edits: dict
    final_report: str
    explainer_output: str
    status: str                  # "pending" | "in_review" | "finalized"

    # ── patient / study metadata ─────────────────────────────────────────────
    patient_id: str
    study_date: str              # ISO "YYYY-MM-DD"

    # ── longitudinal / comparison fields (Phase 10) ──────────────────────────
    prior_image_path: str | None
    prior_study_date: str | None
    prior_findings: dict | None
    comparison_report: str | None
    interval_findings: list | None        # list[IntervalFinding]
    comparison_impression: str | None
    comparison_interval: str | None       # e.g. "3 months"
