"""`triage` node — classifier-driven urgency score for worklist ordering.

Urgency is a weighted sum of pathology probabilities:

    urgency_score = sum(WEIGHT[p] * prob[p] for p in pathologies)

Tier weights are anchored on published CXR worklist-prioritization literature:

  - ACR Actionable Reporting Work Group, three-tier critical-findings framework
    https://www.acr.org/Clinical-Resources/Practice-Parameters-and-Technical-Standards
  - Annarumma et al., "Automated triaging of adult chest radiographs with deep
    artificial neural networks," Radiology 2019.
  - Baltruschat et al., "Smart chest X-ray worklist prioritization using
    artificial intelligence: a clinical workflow simulation," Eur Radiol 2021.

CAVEAT (must stay visible in code + demo): these weights are literature-anchored
DEFAULTS, not site-validated. A real deployment would calibrate them against
local data and radiologist review. This is an acknowledged limitation, not a
hidden one.

Keys below are the exact `torchxrayvision.datasets.default_pathologies` strings
(note: "Effusion", "Pleural_Thickening", "Lung Lesion", "Lung Opacity",
"Enlarged Cardiomediastinum").
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# tier label -> (weight, time sensitivity, [pathologies])
TIERS: Dict[str, Tuple[float, str, List[str]]] = {
    "Critical": (1.0, "Immediate communication", ["Pneumothorax", "Pneumonia"]),
    "Urgent": (0.6, "Within hours",
               ["Effusion", "Consolidation", "Edema", "Lung Lesion", "Mass"]),
    "Important": (0.4, "Same-day to days",
                  ["Cardiomegaly", "Nodule", "Infiltration", "Lung Opacity",
                   "Fracture", "Enlarged Cardiomediastinum", "Pleural_Thickening"]),
    "Chronic": (0.2, "Follow-up", ["Atelectasis", "Emphysema", "Fibrosis", "Hernia"]),
}

# flat pathology -> weight lookup
WEIGHTS: Dict[str, float] = {
    p: weight for weight, _sens, paths in TIERS.values() for p in paths
}


def urgency_score(findings: Dict[str, float]) -> float:
    """Weighted sum of pathology probabilities. Unknown keys contribute 0."""
    return sum(WEIGHTS.get(p, 0.0) * float(prob) for p, prob in findings.items())


def top_findings(findings: Dict[str, float], n: int = 3) -> List[Tuple[str, float]]:
    """The n highest-probability findings, descending."""
    return sorted(findings.items(), key=lambda kv: kv[1], reverse=True)[:n]


def tier_of(pathology: str) -> str:
    """Return the tier label for a pathology (or 'Unknown')."""
    for label, (_w, _s, paths) in TIERS.items():
        if pathology in paths:
            return label
    return "Unknown"


def validate_coverage() -> None:
    """Assert the tier map covers exactly the 18 TorchXRayVision pathologies.

    Imported lazily so the UI can import this module without torch.
    """
    import torchxrayvision as xrv

    expected = set(xrv.datasets.default_pathologies)
    covered = set(WEIGHTS)
    assert covered == expected, (
        f"tier map mismatch:\n missing: {expected - covered}\n extra: {covered - expected}"
    )


def triage(state: dict) -> dict:
    """LangGraph node: read ``state['findings']`` → write ``state['urgency_score']``."""
    return {"urgency_score": urgency_score(state["findings"])}
