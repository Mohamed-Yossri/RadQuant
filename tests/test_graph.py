"""Phase 7 unit tests: graph wiring + routing logic (no model inference)."""

from radquant.graph import build_graph, route_after_review, ingest, review


def test_graph_compiles_with_all_nodes():
    g = build_graph(interrupt=False)
    nodes = set(g.get_graph().nodes)
    for n in ("ingest", "classify", "triage", "visualize", "draft", "review", "qc"):
        assert n in nodes, f"missing node {n}"


def test_route_after_review():
    assert route_after_review({"action": "regenerate"}) == "draft"
    assert route_after_review({"action": "finalize"}) == "qc"
    assert route_after_review({}) == "qc"  # default = finalize/qc


def test_ingest_png_passthrough():
    out = ingest({"image_path": "/some/study.png"})
    assert out == {"dicom_metadata": {}}  # no conversion, no path change


def test_review_folds_draft_when_no_edits():
    out = review({"draft_findings": "Clear lungs.", "draft_impression": "Normal."})
    assert "FINDINGS: Clear lungs." in out["final_report"]
    assert "IMPRESSION: Normal." in out["final_report"]


def test_review_keeps_radiologist_edits():
    out = review({"final_report": "EDITED", "draft_findings": "x"})
    assert out == {}  # existing final_report is preserved untouched
