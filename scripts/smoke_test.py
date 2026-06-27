"""
scripts/smoke_test.py — End-to-end stack validation.
Usage: python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PASS = "✓"
FAIL = "✗"


def check(label: str, fn):
    try:
        fn()
        print(f"  {PASS}  {label}")
        return True
    except Exception as exc:
        print(f"  {FAIL}  {label} — {exc}")
        return False


print("\n═══════════════════════════════════════")
print("  RadQuant smoke test")
print("═══════════════════════════════════════\n")

results = []

# 1. imports
def _imports():
    import radquant
    from radquant.state import CaseState
    from radquant.worklist import Worklist
    from radquant.nodes.classify import classify_node
    from radquant.nodes.triage import triage_node
    from radquant.nodes.compare import comparison_node
    from radquant.nodes.qc import qc_node
    from radquant.nodes.explain import explain_node
    from radquant.graph import build_graph

results.append(check("imports", _imports))

# 2. worklist CRUD
def _worklist():
    import tempfile, os
    from PIL import Image
    from radquant.worklist import Worklist
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        img = tmp / "test.png"
        Image.new("RGB", (64, 64)).save(img)
        wl = Worklist(tmp / "wl.json")
        cid = wl.add_case(str(img), patient_id="TEST")
        assert wl.has_prior(cid) == False
        assert len(wl.sorted_cases()) == 1

results.append(check("worklist CRUD", _worklist))

# 3. triage scoring
def _triage():
    from radquant.nodes.triage import triage_node
    state = {"findings": {"Pneumothorax": 0.9, "Cardiomegaly": 0.5}, "image_path": "x.png"}
    result = triage_node(state)
    assert result["urgency_tier"] == "Critical"
    assert result["urgency_score"] > 0

results.append(check("triage scoring", _triage))

# 4. compare pass-through
def _compare_passthrough():
    from radquant.nodes.compare import comparison_node
    state = {"case_id": "x", "image_path": "x.png", "prior_image_path": None}
    result = comparison_node(state)
    assert result.get("interval_findings") is None

results.append(check("compare pass-through (no prior)", _compare_passthrough))

# 5. compute_interval
def _interval():
    from radquant.nodes.compare import compute_interval
    assert compute_interval("2024-09-15", "2025-03-15") == "6 months"
    assert compute_interval("2024-01-01", "2025-01-01") == "1 year"
    assert compute_interval(None, "2025-01-01") == "unknown interval"

results.append(check("compute_interval", _interval))

# 6. JSON parse robustness
def _json_parse():
    import json
    from radquant.nodes.compare import _parse_json_response
    good = json.dumps({"new": [{"finding": "effusion", "detail": "moderate"}],
                       "worsened": [], "improved": [], "resolved": [], "stable": [],
                       "impression": "New effusion."})
    parsed = _parse_json_response("```json\n" + good + "\n```")
    assert parsed["new"][0]["finding"] == "effusion"
    assert isinstance(_parse_json_response("garbage"), dict)

results.append(check("compare JSON parse", _json_parse))

# 7. QC lexical match
def _qc_lexical():
    from radquant.nodes.qc import qc_node
    stub_judge = lambda p: "YES, the report addresses it."
    state = {
        "findings": {"Pneumothorax": 0.85, "Effusion": 0.75},
        "final_report": "No pneumothorax. Blunting of the right costophrenic angle.",
    }
    result = qc_node(state, judge_fn=stub_judge)
    assert result["omissions"] == []

results.append(check("QC lexical (no omissions)", _qc_lexical))

# 8. QC detects real omission
def _qc_omission():
    from radquant.nodes.qc import qc_node
    stub_judge = lambda p: "NO"
    state = {
        "findings": {"Pneumothorax": 0.9},
        "final_report": "The lungs appear clear.",
    }
    result = qc_node(state, judge_fn=stub_judge)
    assert len(result["omissions"]) == 1
    assert "Pneumothorax" in result["omissions"][0]["finding"]

results.append(check("QC detects omission", _qc_omission))

# 9. graph builds
def _graph_builds():
    from radquant.graph import build_graph
    g = build_graph()
    assert g is not None

results.append(check("graph compiles", _graph_builds))

# ── Summary ──────────────────────────────────────────────────────────────────
passed = sum(results)
failed = len(results) - passed
print(f"\n{'═'*39}")
print(f"  {passed}/{len(results)} checks passed" + (f" — {failed} FAILED" if failed else " — all good ✓"))
print()
sys.exit(0 if failed == 0 else 1)
