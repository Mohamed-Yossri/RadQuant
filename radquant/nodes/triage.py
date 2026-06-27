"""
radquant/nodes/triage.py — urgency scoring with literature-anchored weights.

Tier weights anchored on:
- ACR Actionable Reporting Work Group three-tier critical findings framework
- Annarumma et al., Radiology 2019
- Baltruschat et al., European Radiology 2021

CAVEAT: Weights are literature defaults, NOT site-validated. Real deployment
requires calibration against local clinical triage data.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Pathology → (tier_name, weight)
TRIAGE_WEIGHTS: dict[str, tuple[str, float]] = {
    # Critical T1 — immediate
    "Pneumothorax":              ("Critical", 1.0),
    "Pneumonia":                 ("Critical", 1.0),
    # Urgent T2 — within hours
    "Effusion":                  ("Urgent",   0.6),
    "Consolidation":             ("Urgent",   0.6),
    "Edema":                     ("Urgent",   0.6),
    "Lung Lesion":               ("Urgent",   0.6),
    "Mass":                      ("Urgent",   0.6),
    # Important T3 — same day
    "Cardiomegaly":              ("Important", 0.4),
    "Nodule":                    ("Important", 0.4),
    "Infiltration":              ("Important", 0.4),
    "Lung Opacity":              ("Important", 0.4),
    "Fracture":                  ("Important", 0.4),
    "Enlarged Cardiomediastinum":("Important", 0.4),
    "Pleural Thickening":        ("Important", 0.4),
    # Chronic / incidental T4
    "Atelectasis":               ("Chronic",  0.2),
    "Emphysema":                 ("Chronic",  0.2),
    "Fibrosis":                  ("Chronic",  0.2),
    "Hernia":                    ("Chronic",  0.2),
}

TIER_ORDER = {"Critical": 4, "Urgent": 3, "Important": 2, "Chronic": 1}


def triage_node(state: dict) -> dict:
    """
    LangGraph node: compute urgency_score from classifier findings.
    urgency_score = Σ(weight[p] × prob[p])
    """
    findings = state.get("findings") or {}
    score = 0.0
    dominant_tier = "Chronic"
    dominant_order = 0

    for pathology, prob in findings.items():
        # normalise key: strip underscores, title-case
        key = pathology.replace("_", " ").strip()
        if key in TRIAGE_WEIGHTS:
            tier, weight = TRIAGE_WEIGHTS[key]
            score += weight * prob
            if TIER_ORDER.get(tier, 0) > dominant_order:
                dominant_tier = tier
                dominant_order = TIER_ORDER[tier]

    logger.info(
        "triage_node: score=%.3f tier=%s", score, dominant_tier
    )
    return {**state, "urgency_score": round(score, 4), "urgency_tier": dominant_tier}
