"""Prompt template for MedGemma draft report generation (Phase 4).

The draft is *grounded* in the classifier's findings: we hand MedGemma the list
of pathologies the classifier flagged, show it the image, and ask for FINDINGS +
IMPRESSION — explicitly licensing it to visually dismiss findings it cannot see,
while forbidding it from inventing findings the classifier did not detect.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# Pretty labels for the raw TorchXRayVision keys (underscores / casing).
_PRETTY = {
    "Effusion": "pleural effusion",
    "Pleural_Thickening": "pleural thickening",
    "Enlarged Cardiomediastinum": "enlarged cardiomediastinum",
    "Lung Opacity": "lung opacity",
    "Lung Lesion": "lung lesion",
}


def _pretty(name: str) -> str:
    return _PRETTY.get(name, name.replace("_", " ").lower())


def top_findings_above(findings: Dict[str, float], threshold: float = 0.5
                       ) -> List[Tuple[str, float]]:
    """Findings at or above ``threshold``, highest first."""
    return sorted(
        ((k, v) for k, v in findings.items() if v >= threshold),
        key=lambda kv: kv[1], reverse=True,
    )


def format_findings_summary(findings: Dict[str, float], threshold: float = 0.5) -> str:
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


def build_draft_prompt(findings: Dict[str, float], threshold: float = 0.5) -> str:
    """Build the user prompt for one case."""
    summary = format_findings_summary(findings, threshold)
    return (
        "A chest X-ray is provided. An automated classifier reported the following "
        f"candidate findings (probability in parentheses):\n  {summary}\n\n"
        "Write a draft report with exactly two sections, each on its own line and "
        "prefixed with the section header in capitals:\n"
        "FINDINGS: descriptive observations of the image.\n"
        "IMPRESSION: a short interpretive summary.\n\n"
        "Rules:\n"
        "- Address each classifier finding above: if it is visually supported, "
        "describe it; if it is NOT visually supported, you may dismiss it "
        "(e.g. 'no convincing evidence of ...').\n"
        "- Do NOT invent findings the classifier did not report and you cannot see.\n"
        "- If the image is not a standard frontal chest radiograph, say so plainly.\n"
        "Begin your reply directly with 'FINDINGS:'."
    )
