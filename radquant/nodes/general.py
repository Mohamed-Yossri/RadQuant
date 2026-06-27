"""General Medical mode — modality-agnostic analysis via MedGemma alone.

The chest-X-ray workstation layers CXR-specific specialist tools (DenseNet
classifier, grounding, segmentation, triage) on top of MedGemma. This mode runs
**only MedGemma**, so it works on any modality MedGemma was trained on — CT, MRI,
ultrasound, dermatology, fundus, histopathology. The CXR specialist tools are
deliberately NOT used here: they are trained on chest radiographs and would fire
spuriously on other modalities (the out-of-distribution failure mode).

Pipeline: ``detect_modality`` → ``describe`` (domain-templated) → ``vqa`` (ask
anything). The patient explainer (``radquant.nodes.explain``) is reused as-is.
"""

from __future__ import annotations

import re
from typing import Dict

from radquant.models.medgemma import generate

# Canonical modality labels surfaced to the UI.
MODALITIES = [
    "Chest X-ray", "Other X-ray", "CT", "MRI", "Ultrasound",
    "Dermatology photo", "Fundus photo", "Histopathology", "Other",
]

DETECT_PROMPT = (
    "You are a medical-imaging intake assistant. Identify this image.\n"
    "Reply on ONE line in EXACTLY this format and nothing else:\n"
    "Modality: <type>; Region: <body region or tissue>\n"
    "where <type> is one of: chest X-ray, other X-ray, CT, MRI, ultrasound, "
    "dermatology photo, fundus photo, histopathology."
)


def _canon(text: str) -> str:
    """Map MedGemma's free-text modality guess onto a canonical label."""
    c = text.lower()
    if ("chest" in c and "x" in c) or "cxr" in c:
        return "Chest X-ray"
    if "x-ray" in c or "x ray" in c or "radiograph" in c:
        return "Other X-ray"
    if re.search(r"\bct\b", c) or "computed tomography" in c:
        return "CT"
    if "mri" in c or "magnetic" in c:
        return "MRI"
    if "ultrasound" in c or "sonograph" in c or "echo" in c:
        return "Ultrasound"
    if "derm" in c or "skin" in c or "lesion" in c:
        return "Dermatology photo"
    if "fundus" in c or "retina" in c or "ophthalm" in c:
        return "Fundus photo"
    if "histo" in c or "patholog" in c or "h&e" in c or "microscop" in c or "slide" in c:
        return "Histopathology"
    return "Other"


def detect_modality(image_path: str) -> Dict:
    """Return ``{modality, region, is_cxr, raw}`` for any medical image."""
    raw = generate(image_path, DETECT_PROMPT, max_new_tokens=40)
    m = re.search(r"Modality:\s*([^;\n]+)", raw, re.I)
    modality = _canon(m.group(1) if m else raw)
    r = re.search(r"Region:\s*([^\n]+)", raw, re.I)
    region = r.group(1).strip().rstrip(".") if r else ""
    return {
        "modality": modality,
        "region": region,
        "is_cxr": modality == "Chest X-ray",
        "raw": raw.strip(),
    }


def _describe_prompt(modality: str) -> str:
    m = modality.lower()
    if "x-ray" in m or m in ("ct", "mri", "ultrasound"):
        return (
            "Provide a concise, structured radiology read of this image.\n"
            "FINDINGS: systematic observations of what is visible.\n"
            "IMPRESSION: a short interpretive summary.\n"
            "Describe only what you can actually see; do not invent findings. "
            "Begin your reply with 'FINDINGS:'."
        )
    if "dermatology" in m:
        return (
            "Describe this skin lesion for a clinician. Note: asymmetry, border, "
            "color variation, approximate size, and surface/elevation. Then give a "
            "brief differential (most to least likely) and a next-step recommendation. "
            "Do NOT give a definitive diagnosis."
        )
    if "fundus" in m:
        return (
            "Describe this retinal fundus image: optic disc, vessels, macula, and any "
            "microaneurysms, hemorrhages, exudates, or neovascularization. End with a "
            "one-line impression. Do NOT give a definitive diagnosis."
        )
    if "histopath" in m:
        return (
            "Describe this histopathology image: tissue type, architecture, cellularity, "
            "and any notable cytologic features. Avoid a definitive diagnosis."
        )
    return (
        "Describe what this medical image shows in a concise, structured way, noting any "
        "abnormalities that are visible. Avoid a definitive diagnosis."
    )


def describe(image_path: str, modality: str) -> str:
    """Domain-templated structured description (radiology / derm / fundus / path)."""
    return generate(image_path, _describe_prompt(modality), max_new_tokens=384).strip()


def vqa(image_path: str, question: str) -> str:
    """Free-text question answering over the image (MedGemma sees it)."""
    prompt = (
        "Answer this question about the medical image clearly and concisely, based "
        f"only on what is visible. If unsure, say so.\nQuestion: {question}"
    )
    return generate(image_path, prompt, max_new_tokens=256).strip()
