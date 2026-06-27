"""
radquant/nodes/explain.py — Patient-friendly report translation (Phase 6).
Text-only MedGemma path — modality-agnostic (CT, MRI, US, X-ray).
"""

from __future__ import annotations

import logging
import re

from radquant.prompts.explainer import EXPLAINER_PROMPT, GLOSSARY_PARSE_HINT

logger = logging.getLogger(__name__)


def build_glossary(raw_output: str) -> dict[str, str]:
    """Parse GLOSSARY section into {term: definition}."""
    glossary = {}
    if GLOSSARY_PARSE_HINT not in raw_output:
        return glossary
    _, _, gloss_section = raw_output.partition(GLOSSARY_PARSE_HINT)
    for line in gloss_section.strip().splitlines():
        m = re.match(r"\s*[-*]?\s*(.+?):\s*(.+)", line)
        if m:
            glossary[m.group(1).strip()] = m.group(2).strip()
    return glossary


def highlight_html(plain_text: str, glossary: dict) -> str:
    """Wrap glossary terms in <abbr> tags for hover tooltips."""
    html = plain_text
    for term, definition in glossary.items():
        safe_def = definition.replace('"', "&quot;")
        html = re.sub(
            rf"\b({re.escape(term)})\b",
            f'<abbr title="{safe_def}" style="border-bottom:1px dotted #888;cursor:help;">\\1</abbr>',
            html,
            flags=re.IGNORECASE,
        )
    return html


def explain_node(state: dict) -> dict:
    """
    LangGraph node: translate the final (or draft) report to plain language.
    Populates state['explainer_output'].
    """
    from radquant.models.medgemma import MedGemmaModel

    report = state.get("final_report") or (
        f"FINDINGS:\n{state.get('draft_findings', '')}\n\n"
        f"IMPRESSION:\n{state.get('draft_impression', '')}"
    )

    if not report.strip():
        logger.warning("explain_node: no report text")
        return state

    model = MedGemmaModel.get_instance()
    prompt = EXPLAINER_PROMPT.format(report=report)

    try:
        raw = model.generate(prompt=prompt, images=None, max_new_tokens=512)
    except Exception as exc:
        logger.error("explain_node: MedGemma failed — %s", exc)
        return state

    glossary = build_glossary(raw)
    logger.info("explain_node: %d glossary terms extracted", len(glossary))

    return {**state, "explainer_output": raw, "explainer_glossary": glossary}
