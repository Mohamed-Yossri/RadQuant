"""
radquant/nodes/draft.py — MedGemma draft report generation (comparison-aware).
"""

from __future__ import annotations

import logging
import re

from radquant.prompts.draft_report import DRAFT_PROMPT
from radquant.prompts.comparison import DRAFT_COMPARISON_ADDENDUM

logger = logging.getLogger(__name__)

_FINDINGS_RE = re.compile(r"FINDINGS[:\s]*(.*?)(?=IMPRESSION|$)", re.S | re.I)
_IMPRESSION_RE = re.compile(r"IMPRESSION[:\s]*(.*?)$", re.S | re.I)


def _format_findings(findings: dict, threshold: float = 0.3) -> str:
    if not findings:
        return "No significant findings detected by the classifier."
    rows = [
        f"  {k.replace('_', ' ').title()}: {v:.2f}"
        for k, v in sorted(findings.items(), key=lambda x: -x[1])
        if v >= threshold
    ]
    return "\n".join(rows) if rows else "No significant findings detected by the classifier."


def _build_prompt(state: dict) -> str:
    base = DRAFT_PROMPT.format(
        findings_summary=_format_findings(state.get("findings", {})),
    )
    if state.get("comparison_impression"):
        addendum = DRAFT_COMPARISON_ADDENDUM.format(
            prior_date=state.get("prior_study_date", "unknown date"),
            interval=state.get("comparison_interval", "unknown interval"),
            comparison_impression=state["comparison_impression"],
        )
        return base + addendum
    return base


def draft_node(state: dict) -> dict:
    from PIL import Image
    from radquant.models.medgemma import MedGemmaModel

    image_path = state.get("image_path")
    if not image_path:
        logger.error("draft_node: image_path missing")
        return state

    try:
        img = Image.open(image_path).convert("RGB")
    except Exception as exc:
        logger.error("draft_node: image load failed — %s", exc)
        return state

    prompt = _build_prompt(state)
    model = MedGemmaModel.get_instance()
    logger.info("draft_node: generating (comparison=%s) …", bool(state.get("comparison_impression")))

    try:
        raw = model.generate(prompt=prompt, images=[img], max_new_tokens=512)
    except Exception as exc:
        logger.error("draft_node: MedGemma call failed — %s", exc)
        return state

    findings_match = _FINDINGS_RE.search(raw)
    impression_match = _IMPRESSION_RE.search(raw)
    findings = findings_match.group(1).strip() if findings_match else raw.strip()
    impression = impression_match.group(1).strip() if impression_match else ""

    logger.info("draft_node: %d chars findings, %d chars impression", len(findings), len(impression))
    return {**state, "draft_findings": findings, "draft_impression": impression}
