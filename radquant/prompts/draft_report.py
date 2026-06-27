"""Prompt template for MedGemma draft report generation (Phase 4).

The draft is *grounded* in the classifier's findings: we hand MedGemma the list
of pathologies the classifier flagged, show it the image, and ask for FINDINGS +
IMPRESSION — explicitly licensing it to visually dismiss findings it cannot see,
while forbidding it from inventing findings the classifier did not detect.

Accuracy improvement: per-pathology detection thresholds replace a single fixed
value. Critical/urgent pathologies use a lower threshold (higher sensitivity) so
dangerous findings are never silently dropped. Chronic/low-acuity pathologies use
a higher threshold to suppress false positives in the report.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# Pretty labels for the raw TorchXRayVision keys (underscores / casing).
_PRETTY = {
    "Effusion": "pleural effusion",
    "Pleural_Thickening": "pleural thickening",
    "Enlarged Cardiomediastinum": "enlarged cardiomediastinum",
    "Lung Opacity": "lung opacity",
    "Lung Lesion": "lung lesion",
}

# ---------------------------------------------------------------------------
# Per-pathology detection thresholds (accuracy improvement #1).
#
# Rationale (literature-anchored, same philosophy as the triage tier weights):
#   - Critical / immediately life-threatening findings → lower threshold so we
#     never miss them (favour sensitivity over specificity at this stage; the
#     radiologist and the QC node provide the final gate).
#   - Chronic / low-acuity findings → higher threshold to suppress false positives
#     that would pollute the draft and erode radiologist trust.
#
# Default fallback is 0.50 for any pathology not explicitly listed.
# ---------------------------------------------------------------------------
PATHOLOGY_THRESHOLDS: Dict[str, float] = {
    # Critical — immediate action
    "Pneumothorax":              0.35,
    "Pneumonia":                 0.40,
    # Urgent — within hours
    "Effusion":                  0.42,
    "Edema":                     0.45,
    "Consolidation":             0.45,
    "Lung Lesion":               0.45,
    "Mass":                      0.45,
    # Important — same-day to days
    "Cardiomegaly":              0.50,
    "Nodule":                    0.50,
    "Infiltration":              0.50,
    "Lung Opacity":              0.50,
    "Fracture":                  0.48,
    "Enlarged Cardiomediastinum": 0.48,
    "Pleural_Thickening":        0.52,
    # Chronic / follow-up — higher threshold to cut false positives
    "Atelectasis":               0.55,
    "Emphysema":                 0.55,
    "Fibrosis":                  0.58,
    "Hernia":                    0.60,
}

DEFAULT_THRESHOLD: float = 0.50


def _pretty(name: str) -> str:
    return _PRETTY.get(name, name.replace("_", " ").lower())


def pathology_threshold(name: str, global_override: Optional[float] = None) -> float:
    """Return the effective detection threshold for *name*.

    If *global_override* is given it takes precedence (e.g. during evaluation
    sweeps). Otherwise the per-pathology table is consulted, falling back to
    DEFAULT_THRESHOLD.
    """
    if global_override is not None:
        return global_override
    return PATHOLOGY_THRESHOLDS.get(name, DEFAULT_THRESHOLD)


def top_findings_above(
    findings: Dict[str, float],
    threshold: Optional[float] = None,
) -> List[Tuple[str, float]]:
    """Findings that meet their per-pathology threshold, highest probability first.

    Args:
        findings: ``{pathology: probability}`` dict from the classifier.
        threshold: optional global override.  If *None*, per-pathology thresholds
            from :data:`PATHOLOGY_THRESHOLDS` are used.
    """
    result = [
        (k, v)
        for k, v in findings.items()
        if v >= pathology_threshold(k, threshold)
    ]
    return sorted(result, key=lambda kv: kv[1], reverse=True)


def format_findings_summary(
    findings: Dict[str, float],
    threshold: Optional[float] = None,
) -> str:
    """One-line classifier summary, e.g. 'pleural effusion (0.82), cardiomegaly (0.65)'."""
    top = top_findings_above(findings, threshold)
    if not top:
        return "No pathology exceeded the detection threshold."
    return ", ".join(f"{_pretty(k)} ({v:.2f})" for k, v in top)


SYSTEM_PROMPT = (
    "You are assisting a board-certified radiologist by drafting a chest X-ray "
    "report. You are a drafting aid, not the final author. Be concise and use "
    "standard radiology phrasing."
)


def build_draft_prompt(
    findings: Dict[str, float],
    threshold: Optional[float] = None,
) -> str:
    """Build the user prompt for one case.

    Args:
        findings: classifier output ``{pathology: probability}``.
        threshold: optional global threshold override (``None`` → use per-pathology
            table from :data:`PATHOLOGY_THRESHOLDS`).
    """
    summary = format_findings_summary(findings, threshold)
    return (
        "A chest X-ray is provided. An automated classifier reported the following "
        f"candidate findings (probability in parentheses):\n  {summary}\n\n"
        "Write a draft report with exactly two sections, each on its own line and "
        "prefixed with the section header in capitals:\n"
        "FINDINGS: descriptive observations of the image.\n"
        "IMPRESSION: a short interpretive summary.\n\n"
        "Rules:\n"
        "- For each finding listed, specify its laterality (right / left / bilateral)"
        " and approximate zone (upper / mid / lower) if visible.\n"
        "- Estimate severity as mild, moderate, or severe where applicable.\n"
        "- If a finding is visually supported, describe it; if it is NOT visually "
        "supported, explicitly dismiss it (e.g. 'no convincing evidence of ...').\n"
        "- Do NOT invent findings the classifier did not report and you cannot see.\n"
        "- If the image is not a standard frontal chest radiograph, say so plainly.\n"
        "Begin your reply directly with 'FINDINGS:'."
    )
