"""
radquant/nodes/compare.py — Longitudinal Comparison node (Phase 10).

Multi-image MedGemma call: [prior_image, current_image] → structured JSON.
No-op when state["prior_image_path"] is None (backward-compatible).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, date
from typing import Any

logger = logging.getLogger(__name__)

FINDING_THRESHOLD = 0.10


def compute_interval(prior_date_str: str | None, current_date_str: str | None) -> str:
    try:
        fmt = "%Y-%m-%d"
        d1 = datetime.strptime(prior_date_str, fmt).date()
        d2 = datetime.strptime(current_date_str, fmt).date()
        if d2 < d1:
            d1, d2 = d2, d1
        days = (d2 - d1).days
        if days == 0:   return "same day"
        if days < 7:    return f"{days} day{'s' if days != 1 else ''}"
        if days < 30:   w = days // 7;  return f"{w} week{'s' if w != 1 else ''}"
        if days < 365:  m = days // 30; return f"{m} month{'s' if m != 1 else ''}"
        y = days // 365; rm = (days % 365) // 30
        return f"{y} year{'s' if y != 1 else ''}" + (f", {rm} month{'s' if rm != 1 else ''}" if rm else "")
    except (ValueError, TypeError):
        return "unknown interval"


def format_findings_str(findings: dict | None, threshold: float = FINDING_THRESHOLD) -> str:
    if not findings:
        return "None detected above threshold."
    rows = [
        f"  {k.replace('_', ' ').title()}: {v:.2f}"
        for k, v in sorted(findings.items(), key=lambda x: -x[1])
        if v >= threshold
    ]
    return "\n".join(rows) if rows else "None detected above threshold."


def _parse_json_response(raw: str) -> dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    logger.warning("compare_node: JSON parse failed; raw: %.200s", raw)
    return {"new": [], "worsened": [], "improved": [], "resolved": [], "stable": [], "impression": ""}


def _build_interval_findings(parsed: dict) -> list[dict]:
    findings = []
    for change_type in ("new", "worsened", "improved", "resolved", "stable"):
        for item in parsed.get(change_type, []):
            if isinstance(item, dict) and "finding" in item:
                findings.append({
                    "finding": item.get("finding", ""),
                    "change": change_type,
                    "detail": item.get("detail", ""),
                })
    return findings


def comparison_node(state: dict) -> dict:
    """LangGraph node: longitudinal interval comparison."""
    from radquant.models.medgemma import MedGemmaModel
    from radquant.prompts.comparison import COMPARISON_SYSTEM, COMPARISON_USER
    from PIL import Image

    prior_path = state.get("prior_image_path")
    if not prior_path:
        logger.debug("comparison_node: no prior — skipping")
        return state

    current_path = state.get("image_path")
    if not current_path:
        logger.warning("comparison_node: image_path missing — skipping")
        return state

    prior_date = state.get("prior_study_date") or "unknown date"
    current_date = state.get("study_date") or str(date.today())
    interval = compute_interval(prior_date, current_date)
    logger.info("comparison_node: interval=%s", interval)

    try:
        prior_img = Image.open(prior_path).convert("RGB")
        current_img = Image.open(current_path).convert("RGB")
    except Exception as exc:
        logger.error("comparison_node: image load failed — %s", exc)
        return state

    user_prompt = COMPARISON_USER.format(
        prior_date=prior_date,
        current_date=current_date,
        interval=interval,
        prior_findings_str=format_findings_str(state.get("prior_findings")),
        current_findings_str=format_findings_str(state.get("findings")),
    )

    model = MedGemmaModel.get_instance()
    try:
        raw_response = model.generate(
            prompt=user_prompt,
            images=[prior_img, current_img],
            system=COMPARISON_SYSTEM,
            max_new_tokens=512,
        )
    except Exception as exc:
        logger.error("comparison_node: MedGemma failed — %s", exc)
        return state

    parsed = _parse_json_response(raw_response)
    interval_findings = _build_interval_findings(parsed)
    impression = parsed.get("impression", "").strip()

    logger.info("comparison_node: %d findings parsed, impression=%s",
                len(interval_findings), bool(impression))

    return {
        **state,
        "comparison_report": raw_response,
        "interval_findings": interval_findings,
        "comparison_impression": impression,
        "comparison_interval": interval,
        "study_date": state.get("study_date") or current_date,
    }
