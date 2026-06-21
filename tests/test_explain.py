"""Phase 6 unit tests: glossary parsing + HTML highlighting (fast, no model)."""

from radquant.nodes.explain import parse_glossary, highlight_html


def test_parse_glossary_basic():
    raw = ("cardiomegaly :: an enlarged heart\n"
           "pleural effusion :: fluid around the lungs\n")
    g = parse_glossary(raw)
    assert g["cardiomegaly"] == "an enlarged heart"
    assert g["pleural effusion"] == "fluid around the lungs"


def test_parse_glossary_strips_markdown_noise():
    raw = ("- **atelectasis** :: partial lung collapse\n"
           "1. effusion :: fluid\n"
           "this line has no delimiter and is ignored\n")
    g = parse_glossary(raw)
    assert g["atelectasis"] == "partial lung collapse"
    assert g["effusion"] == "fluid"
    assert len(g) == 2


def test_highlight_wraps_terms_with_tooltip():
    report = "There is mild cardiomegaly and a small effusion."
    g = {"cardiomegaly": "enlarged heart", "effusion": "fluid"}
    out = highlight_html(report, g)
    assert "<abbr" in out
    assert 'title="enlarged heart"' in out
    assert out.count("<abbr") == 2  # both terms wrapped


def test_highlight_is_case_insensitive():
    out = highlight_html("CARDIOMEGALY noted.", {"cardiomegaly": "enlarged heart"})
    assert "<abbr" in out and "CARDIOMEGALY" in out  # original casing preserved


def test_highlight_escapes_html_in_report_and_defs():
    out = highlight_html("a <script> b", {"b": 'x"y'})
    assert "&lt;script&gt;" in out          # report HTML escaped
    assert "&quot;" in out                  # definition quote escaped


def test_highlight_no_terms_returns_escaped_report():
    out = highlight_html("plain text & stuff", {})
    assert out == "plain text &amp; stuff"
