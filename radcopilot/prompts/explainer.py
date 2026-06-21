"""Prompts for the patient-friendly explainer (Phase 6).

Modality-agnostic: these operate on report TEXT only, so they work for CT, MRI,
ultrasound, etc. — not just chest X-ray.
"""

from __future__ import annotations

EXPLAINER_SYSTEM = (
    "You explain radiology reports to patients who have no medical background, "
    "using only everyday words. You are producing a DRAFT for a radiologist to "
    "approve before it reaches a patient. Keep every finding and exactly how "
    "serious it is; do not add reassurance, advice, or alarm that is not in the "
    "original, and never invent findings or recommendations."
)


def build_explainer_prompt(report: str) -> str:
    return (
        "Explain what this radiology report means in plain, everyday language. Do "
        "NOT copy the report's technical wording — replace every medical term with "
        "simple words (for example, say 'bleeding in the brain' instead of "
        "'intraparenchymal hemorrhage'). Keep every finding and how serious it is. "
        "Do not add any advice the report does not contain. Write a few short "
        "sentences, with no headings and no medical jargon.\n\n"
        "Report:\n---\n" + report + "\n---\nPlain explanation:"
    )


def build_glossary_prompt(report: str) -> str:
    return (
        "From the radiology report below, list the medical terms a layperson would "
        "not understand. For each, give a one-sentence plain-language definition.\n"
        "Output ONE term per line in EXACTLY this format:\n"
        "term :: definition\n"
        "Only include terms that literally appear in the report. No bullets, no "
        "numbering, no extra text.\n\nREPORT:\n---\n" + report + "\n---"
    )
