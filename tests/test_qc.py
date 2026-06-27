"""tests/test_qc.py — Unit tests for omission QC node."""

import pytest
from radquant.nodes.qc import qc_node, _lexical_match


YES_JUDGE = lambda p: "YES, addressed."
NO_JUDGE  = lambda p: "NO"


def test_no_omission_when_addressed_lexically():
    state = {"findings": {"Pneumothorax": 0.85},
             "final_report": "No pneumothorax identified."}
    result = qc_node(state, judge_fn=YES_JUDGE)
    assert result["omissions"] == []


def test_synonym_match_no_omission():
    state = {"findings": {"Effusion": 0.80},
             "final_report": "Blunting of the right costophrenic angle is noted."}
    result = qc_node(state, judge_fn=YES_JUDGE)
    assert result["omissions"] == []


def test_omission_detected():
    state = {"findings": {"Pneumothorax": 0.90},
             "final_report": "The lungs appear clear."}
    result = qc_node(state, judge_fn=NO_JUDGE)
    assert len(result["omissions"]) == 1
    assert "Pneumothorax" in result["omissions"][0]["finding"]


def test_below_threshold_not_flagged():
    state = {"findings": {"Pneumothorax": 0.60},
             "final_report": "The lungs appear clear."}
    result = qc_node(state, judge_fn=NO_JUDGE)
    assert result["omissions"] == []


def test_empty_report():
    state = {"findings": {"Effusion": 0.9}, "final_report": ""}
    result = qc_node(state, judge_fn=NO_JUDGE)
    assert result["omissions"] == []


def test_lexical_match_direct():
    assert _lexical_match("Pneumothorax", "There is a large pneumothorax on the left.")
    assert not _lexical_match("Pneumothorax", "The lungs appear clear.")
    assert _lexical_match("Effusion", "Blunting of the costophrenic angle.")
