"""Streamlit explainer page — any report → plain-language patient draft.

Modality-agnostic (CT, MRI, US, X-ray). Run standalone:
    streamlit run radcopilot/ui/explainer.py
"""

from __future__ import annotations

import streamlit as st

from radcopilot.nodes.explain import explain_report, build_glossary, highlight_html

EXAMPLE = (
    "EXAMINATION: CT abdomen/pelvis with contrast.\n"
    "FINDINGS: A 3.5 cm hypodense lesion in the right hepatic lobe, indeterminate. "
    "Mild splenomegaly. No retroperitoneal lymphadenopathy. Cholelithiasis without "
    "cholecystitis.\nIMPRESSION: Indeterminate hepatic lesion; recommend MRI for "
    "further characterization."
)


def render() -> None:
    st.set_page_config(page_title="RadQuant — Explainer", layout="wide")
    st.title("🗣️ Patient-friendly explainer")
    st.caption("⚠️ **Draft for radiologist approval before sharing with a patient.** "
               "Research/assistive demo — not for clinical use.")

    report = st.text_area("Paste a radiology report (any modality)", value=EXAMPLE,
                          height=200)
    if not st.button("Explain", type="primary"):
        return

    with st.spinner("Translating and building glossary..."):
        plain = explain_report(report)
        glossary = build_glossary(report)

    left, right = st.columns(2)
    with left:
        st.subheader("Original (hover underlined terms)")
        st.markdown(highlight_html(report, glossary), unsafe_allow_html=True)
    with right:
        st.subheader("Plain-language draft")
        st.write(plain)

    if glossary:
        with st.expander(f"Glossary ({len(glossary)} terms)"):
            for term, definition in glossary.items():
                st.markdown(f"- **{term}** — {definition}")


if __name__ == "__main__":
    render()
