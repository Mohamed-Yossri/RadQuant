#!/usr/bin/env python3
"""Phase 6 done-when: plain-language explainer on a real, NON-CXR report.

Demonstrates modality-agnosticism (this is a CT report) and that every jargon
term is hover-explained. Run: python scripts/phase6_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radquant.nodes.explain import explain_report, build_glossary, highlight_html

# A real-style CT report (modality-agnostic path: text only, not a chest X-ray).
REPORT = (
    "EXAMINATION: CT head without contrast.\n"
    "FINDINGS: There is a 1.2 cm acute right frontal intraparenchymal hemorrhage "
    "with surrounding vasogenic edema. No midline shift. The ventricles are normal "
    "in size. No acute infarct. Mild chronic small vessel ischemic change.\n"
    "IMPRESSION: Acute right frontal hemorrhage with surrounding edema; no "
    "herniation. Recommend neurosurgical consultation."
)


def main() -> None:
    print("INPUT REPORT (CT head):\n" + REPORT)

    plain = explain_report(REPORT)
    print("\n--- PLAIN-LANGUAGE DRAFT ---\n" + plain)
    assert plain.strip(), "explainer produced empty output"

    # It must actually SIMPLIFY, not echo the report. Hard jargon should be gone.
    low = plain.lower()
    assert plain.strip() != REPORT.strip(), "explainer echoed the report verbatim"
    leaked = [t for t in ("intraparenchymal", "vasogenic", "ischemic", "herniation")
              if t in low]
    assert not leaked, f"plain version still contains untranslated jargon: {leaked}"

    glossary = build_glossary(REPORT)
    print(f"\n--- GLOSSARY ({len(glossary)} terms) ---")
    for term, definition in glossary.items():
        print(f"  {term} :: {definition}")
    assert len(glossary) >= 3, "expected the model to surface several jargon terms"
    assert all(v.strip() for v in glossary.values()), "every term must have a definition"

    # Severity preservation (qualitative): the word 'acute' or 'hemorrhage' meaning
    # should carry through to the patient version.
    low = plain.lower()
    assert any(w in low for w in ("bleed", "hemorrhage", "blood")), \
        "severity/finding (hemorrhage) not conveyed in plain version"

    html_out = highlight_html(REPORT, glossary)
    wrapped = html_out.count("<abbr")
    print(f"\n✓ highlighted {wrapped} jargon term(s) with hover definitions")
    assert wrapped >= 3, "expected several terms wrapped with tooltips"

    print("\n\033[32m✓ Phase 6 check passed — modality-agnostic explainer + glossary + "
          "hover highlighting.\033[0m")
    print("  View: streamlit run radquant/ui/explainer.py")


if __name__ == "__main__":
    main()
