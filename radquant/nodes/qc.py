"""`qc` node — omission QC: flag high-confidence findings absent from the report.

After the radiologist edits, we re-check each classifier finding whose confidence
exceeds the per-pathology QC threshold against the final report.  A finding is
"addressed" if the report mentions it **or** explicitly rules it out (e.g. "no
pneumothorax").  Two-stage check:

  1. lexical (negation-aware) — does any known synonym appear in the report,
     either affirmatively or with a recognised negation pattern?
     (deterministic, cheap)
  2. LLM judge — if no synonym matched at all, ask MedGemma (text-only) whether
     the report nonetheless addresses the finding (catches phrasing the map missed).

Only findings that survive both stages are reported as omissions.  The judge is
injectable so the logic is unit-testable without loading the model.

Accuracy improvements:
  - Per-pathology QC thresholds (mirrors draft_report.py approach): critical
    findings are flagged from a lower confidence level so omissions are never
    silently ignored.
  - Negation-aware lexical pass: "no effusion", "without pneumothorax",
    "effusion not identified" etc. are correctly treated as the finding being
    addressed rather than missed.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Tuple

from radquant.prompts.draft_report import _pretty, pathology_threshold
from radquant.prompts.synonyms import synonyms_for

Judge = Callable[[str], str]

# ---------------------------------------------------------------------------
# Per-pathology QC thresholds (accuracy improvement: dynamic thresholds).
#
# These are deliberately set *lower* than the draft-report thresholds so the QC
# node is more sensitive — it would rather surface a spurious alert (which the
# radiologist can dismiss) than silently miss a real finding.
# ---------------------------------------------------------------------------
_QC_THRESHOLDS: Dict[str, float] = {
    # Critical — flag even at moderate confidence
    "Pneumothorax":               0.30,
    "Pneumonia":                  0.35,
    # Urgent
    "Effusion":                   0.38,
    "Edema":                      0.40,
    "Consolidation":              0.40,
    "Lung Lesion":                0.40,
    "Mass":                       0.40,
    # Important
    "Cardiomegaly":               0.45,
    "Nodule":                     0.45,
    "Infiltration":               0.45,
    "Lung Opacity":               0.45,
    "Fracture":                   0.43,
    "Enlarged Cardiomediastinum": 0.43,
    "Pleural_Thickening":         0.48,
    # Chronic
    "Atelectasis":                0.55,
    "Emphysema":                  0.55,
    "Fibrosis":                   0.58,
    "Hernia":                     0.60,
}

_QC_DEFAULT_THRESHOLD: float = 0.50

# Negation patterns — must precede the keyword (within ~4 words / 30 chars).
# Pattern is applied case-insensitively to a window around each synonym match.
_NEGATION_PREFIX_RE = re.compile(
    r"\b(no|without|absence\s+of|not|rule[sd]?\s+out|unlikely|negative\s+for)\b",
    re.IGNORECASE,
)
# Negation that *follows* the keyword
_NEGATION_SUFFIX_RE = re.compile(
    r"\b(not\s+(seen|identified|present|evident|visualized|demonstrated|appreciated)"
    r"|cannot\s+be\s+(excluded|confirmed)"
    r")\b",
    re.IGNORECASE,
)


def _qc_threshold(pathology: str, override: Optional[float] = None) -> float:
    """QC-specific per-pathology threshold (lower than draft thresholds)."""
    if override is not None:
        return override
    return _QC_THRESHOLDS.get(pathology, _QC_DEFAULT_THRESHOLD)


def _is_negated(report: str, keyword: str) -> bool:
    """True if *keyword* appears in *report* inside a negation context."""
    for m in re.finditer(re.escape(keyword), report, re.IGNORECASE):
        start, end = m.start(), m.end()
        # Check a 60-char window before the keyword for negation prefix
        prefix_window = report[max(0, start - 60): start]
        if _NEGATION_PREFIX_RE.search(prefix_window):
            return True
        # Check a 60-char window after the keyword for negation suffix
        suffix_window = report[end: end + 60]
        if _NEGATION_SUFFIX_RE.search(suffix_window):
            return True
    return False


def _default_judge(prompt: str) -> str:
    from radquant.models.medgemma import generate

    return generate(None, prompt, max_new_tokens=64)


def build_judge_prompt(report: str, pathology: str) -> str:
    syns = ", ".join(synonyms_for(pathology))
    return (
        "You are checking a chest X-ray report for completeness.\n"
        f"REPORT:\n---\n{report}\n---\n"
        f"Question: does this report mention or address '{_pretty(pathology)}' in "
        "any way — including explicitly ruling it out with phrases such as "
        f"'no {_pretty(pathology)}', 'without {_pretty(pathology)}', or "
        f"'{_pretty(pathology)} not identified'? Equivalent phrasings to "
        f"accept: {syns}.\n"
        "Answer with YES or NO on the first line, then one sentence of justification."
    )


def _judge_says_yes(answer: str) -> bool:
    head = answer.strip().lower()[:8]
    return head.startswith("yes") or head.startswith("**yes")


def is_addressed(report: str, pathology: str, judge: Judge) -> Tuple[bool, str]:
    """Return (addressed, method).

    A finding is considered addressed if any synonym appears in the report
    (whether stated affirmatively *or* negated explicitly).  Negation is
    detected via :func:`_is_negated`.  If no synonym matched at all, the LLM
    judge is consulted.
    """
    report_l = report.lower()
    for syn in synonyms_for(pathology):
        if syn in report_l:
            # The term appears — check whether it's negated
            if _is_negated(report_l, syn):
                return True, f"lexical-negation:'{syn}'"
            return True, f"lexical:'{syn}'"
    answer = judge(build_judge_prompt(report, pathology))
    return _judge_says_yes(answer), f"llm:{answer.strip()[:60]!r}"


def suggest(pathology: str, confidence: float) -> str:
    first = synonyms_for(pathology)[0]
    return (f"Classifier flagged {_pretty(pathology)} at {confidence:.2f} but the "
            f"report does not address it. Consider documenting or explicitly "
            f"excluding it (e.g. '{first}').")


def find_omissions(
    report: str,
    findings: Dict[str, float],
    threshold: Optional[float] = None,
    judge: Optional[Judge] = None,
) -> List[dict]:
    """List omissions: findings above their QC threshold not addressed in report.

    Args:
        report: the final (or draft) radiology report text.
        findings: ``{pathology: probability}`` from the classifier.
        threshold: optional global confidence override; ``None`` → per-pathology
            table from :data:`_QC_THRESHOLDS`.
        judge: injectable LLM judge (default: MedGemma text-only).
    """
    judge = judge or _default_judge
    omissions: List[dict] = []
    for path, conf in sorted(findings.items(), key=lambda kv: kv[1], reverse=True):
        if conf <= _qc_threshold(path, threshold):
            continue
        addressed, method = is_addressed(report, path, judge)
        if not addressed:
            omissions.append({
                "finding": path,
                "confidence": round(float(conf), 3),
                "suggestion": suggest(path, conf),
                "method": method,
            })
    return omissions


def qc(state: dict) -> dict:
    """LangGraph node: final_report + findings → omissions."""
    report = state.get("final_report") or ""
    omissions = find_omissions(report, state.get("findings", {}))
    return {"omissions": omissions}
