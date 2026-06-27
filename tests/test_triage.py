"""tests/test_triage.py — Unit tests for triage node."""

import pytest
from radquant.nodes.triage import triage_node, TRIAGE_WEIGHTS


def test_pneumothorax_critical():
    state = {"findings": {"Pneumothorax": 0.9}, "image_path": "x.png"}
    result = triage_node(state)
    assert result["urgency_tier"] == "Critical"
    assert result["urgency_score"] == pytest.approx(0.9, abs=0.01)


def test_multiple_findings_sum():
    state = {"findings": {"Pneumothorax": 1.0, "Effusion": 0.5}, "image_path": "x.png"}
    result = triage_node(state)
    # 1.0*1.0 + 0.5*0.6 = 1.3
    assert result["urgency_score"] == pytest.approx(1.3, abs=0.01)
    assert result["urgency_tier"] == "Critical"


def test_chronic_only():
    state = {"findings": {"Atelectasis": 0.7, "Emphysema": 0.5}, "image_path": "x.png"}
    result = triage_node(state)
    assert result["urgency_tier"] == "Chronic"


def test_empty_findings():
    state = {"findings": {}, "image_path": "x.png"}
    result = triage_node(state)
    assert result["urgency_score"] == 0.0
    assert result["urgency_tier"] == "Chronic"


def test_unknown_pathology_ignored():
    state = {"findings": {"UnknownPathology": 0.99}, "image_path": "x.png"}
    result = triage_node(state)
    assert result["urgency_score"] == 0.0
