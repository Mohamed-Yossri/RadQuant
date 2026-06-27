"""Phase 4 unit tests: draft parsing + findings summary (fast, no model)."""

from radquant.nodes.draft import parse_sections
from radquant.prompts.draft_report import format_findings_summary, top_findings_above


def test_parse_plain_headers():
    text = "FINDINGS: Mild cardiomegaly. IMPRESSION: Mild heart failure."
    f, i = parse_sections(text)
    assert f == "Mild cardiomegaly."
    assert i == "Mild heart failure."


def test_parse_markdown_headers_multiline():
    text = ("**FINDINGS:**\nThe lungs are clear.\nNo effusion.\n\n"
            "**IMPRESSION:**\nNo acute process.")
    f, i = parse_sections(text)
    assert "lungs are clear" in f.lower()
    assert "no effusion" in f.lower()
    assert i.lower().startswith("no acute process")
    assert "impression" not in f.lower()  # findings must not bleed into impression


def test_parse_missing_impression_falls_back():
    f, i = parse_sections("FINDINGS: Something here.")
    assert "something here" in f.lower()
    assert i == ""


def test_findings_summary_orders_and_filters():
    findings = {"Effusion": 0.82, "Cardiomegaly": 0.65, "Nodule": 0.10}
    summary = format_findings_summary(findings, threshold=0.5)
    assert summary.index("pleural effusion") < summary.index("cardiomegaly")  # sorted desc
    assert "nodule" not in summary  # below threshold filtered out


def test_findings_summary_empty():
    assert "threshold" in format_findings_summary({"Nodule": 0.1}, 0.5).lower()


def test_top_findings_above():
    # With explicit threshold override
    out = top_findings_above({"A": 0.9, "B": 0.4, "C": 0.6}, threshold=0.5)
    assert [k for k, _ in out] == ["A", "C"]


def test_per_pathology_threshold_pneumothorax():
    """Pneumothorax at 0.36 is above its per-pathology threshold (0.35) → included."""
    from radquant.prompts.draft_report import top_findings_above
    findings = {"Pneumothorax": 0.36, "Hernia": 0.55}  # Hernia threshold is 0.60
    out = top_findings_above(findings)   # no global override → use per-pathology
    labels = [k for k, _ in out]
    assert "Pneumothorax" in labels, "Pneumothorax at 0.36 should exceed threshold 0.35"
    assert "Hernia" not in labels, "Hernia at 0.55 should be below its threshold 0.60"
