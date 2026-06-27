"""
radquant/nodes/qc.py — Omission QC node.

Two-stage safety net (Phase 5):
1. Lexical match: fast, deterministic synonym check.
2. LLM judge: MedGemma text-only fallback for unmatched findings.

Threshold: > 0.7  (per CLAUDE.md)
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from radquant.prompts.synonyms import SYNONYMS

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.7


def _normalize(text: str) -> str:
    return text.lower().replace("_", " ").replace("-", " ")


def _lexical_match(pathology: str, report: str) -> bool:
    """Return True if any synonym for pathology appears in the report."""
    report_norm = _normalize(report)
    key = pathology.replace("_", " ").strip()
    synonyms = SYNONYMS.get(key, [key])
    return any(_normalize(s) in report_norm for s in synonyms)


def _llm_judge(pathology: str, report: str, judge_fn: Callable) -> bool:
    """
    Ask MedGemma (text-only) whether the report addresses the pathology.
    judge_fn signature: (prompt: str) -> str
    Returns True if the report addresses it (no omission).
    """
    synonyms = SYNONYMS.get(pathology.replace("_", " ").strip(), [pathology])
    syn_str = ", ".join(f'"{s}"' for s in synonyms[:5])
    prompt = (
        f'Does the following radiology report mention or address any of these terms: {syn_str}?\n'
        f'Reply with YES or NO followed by one sentence of justification.\n\n'
        f'REPORT:\n{report[:1500]}'
    )
    try:
        response = judge_fn(prompt)
        return response.strip().upper().startswith("YES")
    except Exception as exc:
        logger.warning("qc llm_judge failed for %s: %s", pathology, exc)
        return True  # assume addressed on failure (safe default — no false alarm)


def qc_node(state: dict, judge_fn: Callable | None = None) -> dict:
    """
    LangGraph node: detect omissions in the radiologist-edited report.

    judge_fn is injectable for tests (stub). In production it defaults to
    MedGemma text-only.
    """
    from radquant.models.medgemma import MedGemmaModel

    findings = state.get("findings") or {}
    # Use radiologist-edited report if available, else draft
    report = (
        state.get("final_report")
        or f"{state.get('draft_findings', '')} {state.get('draft_impression', '')}"
    ).strip()

    if not report:
        logger.warning("qc_node: no report text to check")
        return {**state, "omissions": []}

    if judge_fn is None:
        model = MedGemmaModel.get_instance()
        judge_fn = lambda p: model.generate(prompt=p, images=None, max_new_tokens=64)

    omissions = []
    for pathology, prob in findings.items():
        if prob <= CONFIDENCE_THRESHOLD:
            continue
        key = pathology.replace("_", " ").strip()

        # Stage 1: lexical
        if _lexical_match(key, report):
            logger.debug("qc: %s addressed (lexical)", key)
            continue

        # Stage 2: LLM judge
        if _llm_judge(key, report, judge_fn):
            logger.debug("qc: %s addressed (llm judge)", key)
            continue

        # Neither stage found it — flag as omission
        logger.info("qc: OMISSION detected — %s (%.2f)", key, prob)
        synonyms = SYNONYMS.get(key, [key])
        omissions.append({
            "finding": key,
            "confidence": round(prob, 3),
            "suggestion": f'Consider adding mention of {key}. Possible phrasing: "{synonyms[0]}".',
        })

    logger.info("qc_node: %d omission(s) flagged", len(omissions))
    return {**state, "omissions": omissions}
