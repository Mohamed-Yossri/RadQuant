"""`draft` node — MedGemma drafts FINDINGS + IMPRESSION grounded in findings."""

from __future__ import annotations

import re
from typing import Dict, Tuple

from radquant.models.medgemma import generate
from radquant.prompts.draft_report import build_draft_prompt, SYSTEM_PROMPT

# Match a section header like "FINDINGS:", "**FINDINGS:**", "Findings -" etc.
_FINDINGS_RE = re.compile(r"(?is)findings\s*[:\-]\s*(.*?)(?=\**\s*impression\s*[:\-]|\Z)")
_IMPRESSION_RE = re.compile(r"(?is)impression\s*[:\-]\s*(.*?)\Z")


def _clean(text: str) -> str:
    return text.strip().strip("*").strip()


def parse_sections(text: str) -> Tuple[str, str]:
    """Split a draft into (findings, impression).

    Falls back gracefully: if headers are missing, the whole text becomes the
    findings and the impression is left empty.
    """
    f = _FINDINGS_RE.search(text)
    i = _IMPRESSION_RE.search(text)
    findings = _clean(f.group(1)) if f else _clean(text)
    impression = _clean(i.group(1)) if i else ""
    return findings, impression


def draft_report(image_path: str, findings: Dict[str, float], threshold: float = 0.5,
                 max_new_tokens: int = 512) -> Tuple[str, str, str]:
    """Generate a draft. Returns (findings_text, impression_text, raw_output)."""
    prompt = build_draft_prompt(findings, threshold)
    raw = generate(image_path, prompt, max_new_tokens=max_new_tokens, system=SYSTEM_PROMPT)
    f_text, i_text = parse_sections(raw)
    return f_text, i_text, raw


def draft(state: dict) -> dict:
    """LangGraph node: image + findings → draft_findings, draft_impression."""
    f_text, i_text, _ = draft_report(state["image_path"], state["findings"])
    return {"draft_findings": f_text, "draft_impression": i_text}
