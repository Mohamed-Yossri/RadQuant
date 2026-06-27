"""
scripts/phase10_check.py — Phase 10 (Longitudinal Comparison) verification.
Usage:
    python scripts/phase10_check.py                    # with GPU
    RADQUANT_SKIP_MODEL=1 python scripts/phase10_check.py  # stub, no GPU
"""

from __future__ import annotations

import json, os, sys, tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image
from radquant.nodes.compare import (
    comparison_node, compute_interval, _parse_json_response, _build_interval_findings,
)
from radquant.worklist import Worklist

SKIP = os.environ.get("RADQUANT_SKIP_MODEL") == "1"
P, F = "✓", "✗"
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  {P if ok else F}  {name}" + (f" — {detail}" if detail else ""))


def mkpng(path):
    Image.new("RGB", (64, 64), (100, 100, 100)).save(path)


def good_resp():
    return json.dumps({
        "new": [{"finding": "right pleural effusion", "detail": "moderate"}],
        "worsened": [{"finding": "cardiomegaly", "detail": "CTR 0.58"}],
        "improved": [], "resolved": [{"finding": "atelectasis", "detail": "cleared"}],
        "stable": [], "impression": "Interval development of right pleural effusion.",
    })


print("\n[1] compute_interval")
for prior, curr, expected in [
    ("2025-01-01", "2025-01-01", "same day"),
    ("2025-01-01", "2025-01-04", "3 days"),
    ("2025-01-01", "2025-04-01", "3 months"),
    ("2024-01-01", "2025-01-01", "1 year"),
    ("bad", "2025-01-01", "unknown interval"),
    (None, "2025-01-01", "unknown interval"),
]:
    check(f"interval({prior},{curr})=={expected}", compute_interval(prior, curr) == expected)

print("\n[2] JSON parsing")
p = _parse_json_response(good_resp())
check("plain JSON", bool(p.get("new")))
check("fenced JSON", bool(_parse_json_response("```json\n"+good_resp()+"\n```").get("new")))
check("garbage → dict", isinstance(_parse_json_response("not json"), dict))

print("\n[3] Worklist prior linking")
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    mkpng(tmp/"prior.png"); mkpng(tmp/"current.png")
    wl = Worklist(tmp/"wl.json")
    pid = wl.add_case(str(tmp/"prior.png"), patient_id="P001", study_date="2024-09-15")
    cid = wl.add_case(str(tmp/"current.png"), patient_id="P001", study_date="2025-03-15")
    wl.link_prior(cid, pid)
    check("prior_image_path set", wl.cases[cid]["prior_image_path"] is not None)
    check("prior_study_date set", wl.cases[cid]["prior_study_date"] == "2024-09-15")
    check("has_prior True", wl.has_prior(cid))
    check("get_same_patient", len(wl.get_same_patient_cases("P001", exclude=cid)) == 1)
    wl.unlink_prior(cid)
    check("unlink clears", wl.cases[cid]["prior_image_path"] is None)
    try:
        wl.link_prior(cid, cid)
        check("self-link raises", False)
    except ValueError:
        check("self-link raises", True)

print("\n[4] comparison_node pass-through")
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); mkpng(tmp/"c.png")
    state = {"case_id":"x","image_path":str(tmp/"c.png"),"prior_image_path":None}
    check("no prior → passthrough", comparison_node(state).get("interval_findings") is None)

print("\n[5] comparison_node stubbed MedGemma")
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); mkpng(tmp/"p.png"); mkpng(tmp/"c.png")
    state = {
        "case_id":"y","image_path":str(tmp/"c.png"),"prior_image_path":str(tmp/"p.png"),
        "prior_study_date":"2024-09-15","study_date":"2025-03-15",
        "findings":{"Pleural Effusion":0.82},"prior_findings":{},
    }
    stub = MagicMock(); stub.generate.return_value = good_resp()
    with patch("radquant.nodes.compare.MedGemmaModel.get_instance", return_value=stub):
        result = comparison_node(state)
    check("interval=6 months", result.get("comparison_interval") == "6 months")
    check("impression populated", bool(result.get("comparison_impression")))
    check("interval_findings list", isinstance(result.get("interval_findings"), list))
    new_items = [f for f in result["interval_findings"] if f["change"]=="new"]
    check("new finding present", len(new_items)==1)
    check("finding name correct", new_items[0]["finding"]=="right pleural effusion")

print("\n[6] MedGemma model failure → graceful")
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp); mkpng(tmp/"p.png"); mkpng(tmp/"c.png")
    state = {"case_id":"z","image_path":str(tmp/"c.png"),"prior_image_path":str(tmp/"p.png"),
             "prior_study_date":"2024-09-15","study_date":"2025-03-15","findings":{}}
    bad = MagicMock(); bad.generate.side_effect = RuntimeError("OOM")
    with patch("radquant.nodes.compare.MedGemmaModel.get_instance", return_value=bad):
        result = comparison_node(state)
    check("OOM → no crash, no findings", result.get("interval_findings") is None)

passed = sum(1 for _, ok in results if ok)
failed = len(results) - passed
print(f"\n{'='*45}")
print(f"Phase 10: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
