"""`explain` node — plain-language, modality-agnostic report translation.

Two products from one report:
  1. a plain-language patient version (MedGemma text-only), and
  2. a glossary {jargon term -> definition} used to add hover-explanations.

Both run on report TEXT only, so the explainer works for any modality (CT, MRI,
ultrasound, X-ray). This is a DRAFT for radiologist approval, never direct-to-
patient output.
"""

from __future__ import annotations

import html
import re
from typing import Dict, Tuple

from radquant.prompts.explainer import (
    EXPLAINER_SYSTEM,
    build_explainer_prompt,
    build_glossary_prompt,
)


def explain_report(report: str, max_new_tokens: int = 512) -> str:
    """Return a plain-language version of the report (severity preserved)."""
    from radquant.models.medgemma import generate

    return generate(None, build_explainer_prompt(report),
                    max_new_tokens=max_new_tokens, system=EXPLAINER_SYSTEM)


def parse_glossary(text: str) -> Dict[str, str]:
    """Parse 'term :: definition' lines into a dict (robust to markdown noise)."""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip().lstrip("-*0123456789. ").strip()
        if "::" not in line:
            continue
        term, _, definition = line.partition("::")
        term, definition = term.strip().strip("*").strip(), definition.strip()
        if term and definition:
            out[term] = definition
    return out


def build_glossary(report: str, max_new_tokens: int = 512) -> Dict[str, str]:
    """Ask MedGemma to extract jargon terms + definitions from the report."""
    from radquant.models.medgemma import generate

    raw = generate(None, build_glossary_prompt(report), max_new_tokens=max_new_tokens)
    return parse_glossary(raw)


def highlight_html(report: str, glossary: Dict[str, str]) -> str:
    """Wrap each glossary term in the report with a hover-tooltip <abbr> tag.

    Pure function (no model). HTML-escapes both the report and the definitions,
    and matches longest terms first so overlapping terms don't double-wrap.
    """
    escaped = html.escape(report)
    for term in sorted(glossary, key=len, reverse=True):
        definition = html.escape(glossary[term], quote=True)
        pattern = re.compile(re.escape(html.escape(term)), re.IGNORECASE)
        replacement = (
            f'<abbr title="{definition}" '
            f'style="text-decoration: underline dotted; cursor: help;">\\g<0></abbr>'
        )
        # Only wrap the FIRST occurrence to keep markup readable.
        escaped = pattern.sub(replacement, escaped, count=1)
    return escaped


def explain(state: dict) -> dict:
    """LangGraph side-call node: report text -> explainer_output (plain text)."""
    report = state.get("final_report") or state.get("draft_findings") or ""
    return {"explainer_output": explain_report(report)}


def explain_with_glossary(report: str) -> Tuple[str, Dict[str, str]]:
    """Convenience: (plain_text, glossary) in one call (used by the UI)."""
    return explain_report(report), build_glossary(report)
