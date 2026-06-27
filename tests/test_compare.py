"""tests/test_compare.py — Unit tests for longitudinal comparison (Phase 10)."""

from __future__ import annotations
import json
from unittest.mock import MagicMock, patch
import pytest
from PIL import Image
from radquant.nodes.compare import (
    comparison_node, compute_interval, format_findings_str,
    _parse_json_response, _build_interval_findings,
)


@pytest.fixture
def tmp_images(tmp_path):
    prior = tmp_path / "prior.png"
    current = tmp_path / "current.png"
    Image.new("RGB", (64, 64), (128, 128, 128)).save(prior)
    Image.new("RGB", (64, 64), (128, 128, 128)).save(current)
    return str(prior), str(current)


def good_resp():
    return json.dumps({
        "new": [{"finding": "right pleural effusion", "detail": "moderate"}],
        "worsened": [{"finding": "cardiomegaly", "detail": "CTR 0.58"}],
        "improved": [],
        "resolved": [{"finding": "atelectasis", "detail": "cleared"}],
        "stable": [{"finding": "vascular congestion", "detail": "unchanged"}],
        "impression": "Interval development of right pleural effusion.",
    })


def stub_model(response):
    m = MagicMock(); m.generate.return_value = response; return m


# ── (a) pass-through ─────────────────────────────────────────────────────────
def test_no_prior_passthrough(tmp_images):
    _, c = tmp_images
    state = {"case_id": "x", "image_path": c, "prior_image_path": None}
    result = comparison_node(state)
    assert result.get("interval_findings") is None

def test_missing_prior_key_passthrough(tmp_images):
    _, c = tmp_images
    assert comparison_node({"case_id":"x","image_path":c}).get("interval_findings") is None


# ── (b) happy path ───────────────────────────────────────────────────────────
@patch("radquant.nodes.compare.MedGemmaModel.get_instance")
def test_comparison_populates_fields(mock_get, tmp_images):
    p, c = tmp_images
    mock_get.return_value = stub_model(good_resp())
    state = {"case_id":"y","image_path":c,"prior_image_path":p,
             "prior_study_date":"2024-09-15","study_date":"2025-03-15",
             "findings":{"Pleural Effusion":0.82},"prior_findings":{}}
    result = comparison_node(state)
    assert result["comparison_interval"] == "6 months"
    assert result["comparison_impression"].startswith("Interval")
    assert isinstance(result["interval_findings"], list)
    assert len(result["interval_findings"]) > 0


# ── (c) compute_interval ─────────────────────────────────────────────────────
@pytest.mark.parametrize("prior,curr,expected", [
    ("2025-01-01","2025-01-01","same day"),
    ("2025-01-01","2025-01-04","3 days"),
    ("2025-01-01","2025-01-10","1 week"),
    ("2025-01-01","2025-04-01","3 months"),
    ("2024-01-01","2025-01-01","1 year"),
    ("2023-01-01","2025-03-01","2 years, 2 months"),
    ("bad","2025-01-01","unknown interval"),
    (None,"2025-01-01","unknown interval"),
])
def test_compute_interval(prior, curr, expected):
    assert compute_interval(prior, curr) == expected


# ── (d) JSON robustness ───────────────────────────────────────────────────────
def test_parse_plain_json():
    p = _parse_json_response(good_resp())
    assert p["new"][0]["finding"] == "right pleural effusion"

def test_parse_fenced_json():
    p = _parse_json_response("```json\n" + good_resp() + "\n```")
    assert p["new"][0]["finding"] == "right pleural effusion"

def test_parse_truncated_returns_dict():
    p = _parse_json_response('{"new": [{"finding": "effusion"')
    assert isinstance(p, dict)

def test_parse_garbage_returns_dict():
    assert isinstance(_parse_json_response("I cannot compare."), dict)


# ── (e) model failure → graceful ─────────────────────────────────────────────
@patch("radquant.nodes.compare.MedGemmaModel.get_instance")
def test_model_failure_graceful(mock_get, tmp_images):
    p, c = tmp_images
    m = MagicMock(); m.generate.side_effect = RuntimeError("OOM")
    mock_get.return_value = m
    state = {"case_id":"z","image_path":c,"prior_image_path":p,
             "prior_study_date":"2024-09-15","study_date":"2025-03-15","findings":{}}
    result = comparison_node(state)
    assert result.get("interval_findings") is None


# ── (f) interval_findings categories ─────────────────────────────────────────
def test_interval_findings_categories():
    parsed = _parse_json_response(good_resp())
    findings = _build_interval_findings(parsed)
    changes = {f["change"] for f in findings}
    assert {"new","worsened","resolved","stable"}.issubset(changes)
    new_items = [f for f in findings if f["change"]=="new"]
    assert new_items[0]["finding"] == "right pleural effusion"


# ── format_findings_str ───────────────────────────────────────────────────────
def test_format_findings_empty():
    assert "None" in format_findings_str(None)
    assert "None" in format_findings_str({})

def test_format_findings_threshold():
    r = format_findings_str({"Effusion":0.82,"Cardiomegaly":0.05}, threshold=0.10)
    assert "Effusion" in r
    assert "Cardiomegaly" not in r
