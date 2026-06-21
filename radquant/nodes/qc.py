"""`qc` node — omission QC: flag high-confidence findings absent from the report.

After the radiologist edits, we re-check each classifier finding with confidence
> 0.7 against the final report. A finding is "addressed" if the report mentions
it OR explicitly rules it out (e.g. "no pneumothorax"). Two-stage check:

  1. lexical — does any known synonym appear in the report? (deterministic, cheap)
  2. LLM judge — if no synonym matched, ask MedGemma (text-only) whether the
     report nonetheless addresses the finding (catches phrasing the map missed).

Only findings that survive both stages are reported as omissions. The judge is
injectable so the logic is unit-testable without loading the model.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from radquant.prompts.draft_report import _pretty
from radquant.prompts.synonyms import synonyms_for

Judge = Callable[[str], str]


def _default_judge(prompt: str) -> str:
    from radquant.models.medgemma import generate

    return generate(None, prompt, max_new_tokens=64)


def build_judge_prompt(report: str, pathology: str) -> str:
    syns = ", ".join(synonyms_for(pathology))
    return (
        "You are checking a chest X-ray report for completeness.\n"
        f"REPORT:\n---\n{report}\n---\n"
        f"Question: does this report mention or address '{_pretty(pathology)}' in "
        "any way — including explicitly ruling it out? Equivalent phrasings to "
        f"accept: {syns}.\n"
        "Answer with YES or NO on the first line, then one sentence of justification."
    )


def _judge_says_yes(answer: str) -> bool:
    head = answer.strip().lower()[:8]
    return head.startswith("yes") or head.startswith("**yes")


def is_addressed(report: str, pathology: str, judge: Judge) -> Tuple[bool, str]:
    """Return (addressed, method). Lexical match first, else the LLM judge."""
    report_l = report.lower()
    for syn in synonyms_for(pathology):
        if syn in report_l:
            return True, f"lexical:'{syn}'"
    answer = judge(build_judge_prompt(report, pathology))
    return _judge_says_yes(answer), f"llm:{answer.strip()[:60]!r}"


def suggest(pathology: str, confidence: float) -> str:
    first = synonyms_for(pathology)[0]
    return (f"Classifier flagged {_pretty(pathology)} at {confidence:.2f} but the "
            f"report does not address it. Consider documenting or explicitly "
            f"excluding it (e.g. '{first}').")


def find_omissions(report: str, findings: Dict[str, float], threshold: float = 0.7,
                   judge: Optional[Judge] = None) -> List[dict]:
    """List omissions: findings with confidence > threshold not addressed in report."""
    judge = judge or _default_judge
    omissions: List[dict] = []
    for path, conf in sorted(findings.items(), key=lambda kv: kv[1], reverse=True):
        if conf <= threshold:
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
