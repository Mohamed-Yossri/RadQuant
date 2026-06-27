"""Phase 5 unit tests: omission QC logic with an injected (stub) judge.

Deterministic — no model load. Covers the three PLAN.md done-when cases plus
threshold and synonym behaviour.
"""

from radquant.nodes.qc import find_omissions

# Stub judges (the LLM is only consulted when no synonym matches lexically).
JUDGE_NO = lambda prompt: "NO. The report does not address it."
JUDGE_YES = lambda prompt: "YES. The report rules it out."


def test_a_pneumothorax_unmentioned_is_flagged():
    report = "The lungs are clear. Heart size is normal."
    oms = find_omissions(report, {"Pneumothorax": 0.8}, judge=JUDGE_NO)
    assert [o["finding"] for o in oms] == ["Pneumothorax"]
    assert oms[0]["confidence"] == 0.8
    assert "pneumothorax" in oms[0]["suggestion"].lower()


def test_b_pneumothorax_ruled_out_is_not_flagged():
    report = "The lungs are clear. No pneumothorax. No effusion."
    # Even with a NO-judge, the lexical match should short-circuit to addressed.
    oms = find_omissions(report, {"Pneumothorax": 0.8}, judge=JUDGE_NO)
    assert oms == []


def test_c_effusion_synonym_is_not_flagged():
    report = "There is blunting of the right costophrenic angle."
    oms = find_omissions(report, {"Effusion": 0.8}, judge=JUDGE_NO)
    assert oms == []


def test_threshold_excludes_low_confidence():
    report = "Lungs clear."
    # Pneumothorax per-pathology QC threshold is 0.30. A score of 0.25 is
    # below it and must be silently ignored (judge never consulted).
    oms = find_omissions(report, {"Pneumothorax": 0.25}, judge=JUDGE_NO)
    assert oms == []


def test_judge_yes_means_addressed():
    report = "Lungs clear."
    oms = find_omissions(report, {"Mass": 0.9}, judge=JUDGE_YES)
    assert oms == []


def test_multiple_findings_sorted_by_confidence():
    report = "Lungs clear."
    oms = find_omissions(report, {"Mass": 0.75, "Pneumonia": 0.95}, judge=JUDGE_NO)
    assert [o["finding"] for o in oms] == ["Pneumonia", "Mass"]  # highest first


def test_negation_is_treated_as_addressed():
    """'No pneumothorax' in the report should count as addressed (negation-aware)."""
    report = "The lungs are clear. No pneumothorax identified. No effusion."
    oms = find_omissions(report, {"Pneumothorax": 0.85}, judge=JUDGE_NO)
    assert oms == [], f"negation not recognised: {oms}"


def test_negation_suffix_is_treated_as_addressed():
    """'Pneumothorax not identified' (suffix negation) should count as addressed."""
    report = "FINDINGS: Pneumothorax not identified. Mild cardiomegaly."
    oms = find_omissions(report, {"Pneumothorax": 0.85}, judge=JUDGE_NO)
    assert oms == [], f"suffix negation not recognised: {oms}"
